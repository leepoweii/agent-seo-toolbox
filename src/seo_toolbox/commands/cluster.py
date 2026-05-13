"""seo cluster — fetch SERPs (cache-first), compute similarity, serve interactive UI.

Lifecycle:
  1. Read keywords + volumes from CSV.
  2. For each keyword: cache lookup (TTL valid → use; else fetch depth=20, upsert).
  3. Compute similarity matrix (full N×N, method per --method flag — default
     `percentage` / Szymkiewicz–Simpson) and shared-count matrix.
  4. Run greedy volume-anchored clustering.
  5. Render Jinja2 template, start http.server on free port, open browser.
  6. Block until POST /save (or 30-min timeout). Write cluster_state.json.
  7. Print final JSON summary to stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seo_toolbox.config import load_config
from seo_toolbox.dataforseo import DataForSEOClient, parse_serp_items
from seo_toolbox.db import SerpCache, make_engine, make_session_factory
from seo_toolbox.grouping import greedy_volume_clustering
from seo_toolbox.registry import Brand, Cache, Cluster, Market, SerpFetch, package_version
from seo_toolbox.similarity import jaccard, percentage, shared_count
from seo_toolbox.url_utils import normalize_url

CLUSTER_DEPTH = SerpFetch.CLUSTER_DEPTH
TTL_DAYS = Cache.SERP_TTL_DAYS
SESSION_SECONDS = Cluster.SESSION_SECONDS
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("cluster", help="Cluster keywords by SERP overlap")
    p.add_argument("keywords_csv",
                   help="CSV file with header 'keyword' (and optional 'volume')")
    p.add_argument("--threshold", type=float, default=None)
    p.add_argument("--method", choices=["jaccard", "percentage"], default=None)
    p.add_argument("--output", default=None,
                   help="Optional output CSV with cluster_id assignments")
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace) -> int:
    cfg = load_config()
    if not (cfg.database_url and cfg.dataforseo_login and cfg.dataforseo_password):
        print(json.dumps({
            "error": "config not set up — run `seo init --check`",
            "code": "config_invalid",
        }))
        return 1
    threshold = args.threshold if args.threshold is not None else cfg.cluster_threshold
    method = args.method or cfg.similarity_method
    keywords, volumes = _read_keywords(args.keywords_csv)
    if not keywords:
        print(json.dumps({"error": "no keywords in CSV", "code": "empty_csv"}))
        return 1
    return asyncio.run(_async_main(cfg, keywords, volumes, threshold, method, args.output))


def _read_keywords(path: str) -> tuple[list[str], dict[str, int]]:
    keywords: list[str] = []
    volumes: dict[str, int] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kw = (row.get("keyword") or "").strip()
            if not kw:
                continue
            keywords.append(kw)
            try:
                volumes[kw] = int(row.get("volume") or 0)
            except (ValueError, TypeError):
                volumes[kw] = 0
    return keywords, volumes


async def _async_main(cfg, keywords, volumes, threshold, method, output_path) -> int:
    engine = make_engine(cfg.database_url)
    factory = make_session_factory(engine)
    client = DataForSEOClient(
        cfg.dataforseo_login, cfg.dataforseo_password, sandbox=cfg.dataforseo_sandbox
    )
    try:
        async with factory() as session:
            result = await run_cluster_pipeline(
                keywords=keywords,
                volumes=volumes,
                session=session,
                client=client,
                threshold=threshold,
                method=method,
                location_code=cfg.location_code,
                language_code=cfg.language_code,
                ttl_days=cfg.serp_ttl_days,
            )
            await session.commit()
    finally:
        await engine.dispose()

    runid = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    state_dir = Path("/tmp") / f"seo-cluster-{runid}"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "cluster_state.json"

    final_state = _serve_and_wait(
        state_path=state_path,
        keywords=keywords,
        volumes=volumes,
        result=result,
        domains={
            "own": cfg.own_domain,
            "competitors": cfg.competitor_domains,
            "authority_tlds": cfg.authority_tlds,
        },
        threshold=threshold,
    )

    print(json.dumps({
        "state_path": str(state_path),
        "clusters": final_state["clusters"],
        "ungrouped": final_state["ungrouped"],
        "threshold_used": final_state.get("threshold", threshold),
    }, ensure_ascii=False, default=str))

    if output_path:
        _write_output_csv(output_path, final_state)
    return 0


async def run_cluster_pipeline(
    *,
    keywords: list[str],
    volumes: dict[str, int],
    session: AsyncSession,
    client: Any,
    threshold: float,
    method: str,
    location_code: int = Market.LOCATION_CODE,
    language_code: str = Market.LANGUAGE_CODE,
    ttl_days: int = TTL_DAYS,
) -> dict[str, Any]:
    serp_urls: dict[str, list[str]] = {}
    serp_features: dict[str, dict[str, Any]] = {}
    for kw in keywords:
        urls, features = await _fetch_or_get_cached(
            kw, session, client, location_code, language_code, ttl_days
        )
        serp_urls[kw] = urls
        serp_features[kw] = features

    matrix = _compute_matrix(keywords, serp_urls, method)
    shared_matrix = _compute_shared(keywords, serp_urls)
    grouping = greedy_volume_clustering(
        keywords=keywords, volumes=volumes,
        similarity_matrix=matrix, threshold=threshold,
    )

    return {
        "matrix": matrix,
        "shared_count_matrix": shared_matrix,
        "serps": serp_urls,
        "serp_features": serp_features,
        "clusters": [
            {"primary": c.primary, "members": c.members, "volume": c.volume}
            for c in grouping.clusters
        ],
        "ungrouped": grouping.ungrouped,
    }


def _extract_features(serp_data: dict) -> dict[str, Any]:
    """Pull AI Overview / Featured Snippet / PAA / organic from a serp_data dict.
    Stable shape regardless of which add-ons are present."""
    return {
        "ai_overview": serp_data.get("ai_overview"),
        "featured_snippet": serp_data.get("featured_snippet"),
        "paa": serp_data.get("people_also_ask") or [],
        "organic": (serp_data.get("organic_results") or [])[:10],
    }


async def _fetch_or_get_cached(
    kw, session, client, loc, lang, ttl_days
) -> tuple[list[str], dict[str, Any]]:
    res = await session.execute(
        select(SerpCache).where(
            SerpCache.keyword == kw,
            SerpCache.location_code == loc,
            SerpCache.language_code == lang,
        )
    )
    row = res.scalar_one_or_none()
    if row and row.expires_at and datetime.now() < row.expires_at:
        data = row.serp_data or {}
        organic = data.get("organic_results", [])
        urls = [normalize_url(o.get("url")) for o in organic[:10] if o.get("url")]
        return urls, _extract_features(data)

    api = await client.fetch_serp(
        keyword=kw, location_code=loc, language_code=lang, depth=CLUSTER_DEPTH,
    )
    parsed = parse_serp_items(api["items"])
    parsed["metadata"] = {"depth_fetched": CLUSTER_DEPTH}
    parsed["item_types"] = api.get("item_types", [])

    now = datetime.now()
    expires = now + timedelta(days=ttl_days)
    if row:
        row.serp_data = parsed
        row.total_results = api.get("total_results")
        row.fetched_at = now
        row.expires_at = expires
    else:
        session.add(SerpCache(
            keyword=kw, location_code=loc, language_code=lang,
            serp_data=parsed, total_results=api.get("total_results"),
            fetched_at=now, expires_at=expires,
        ))
    await session.flush()
    urls = [normalize_url(o.get("url")) for o in parsed["organic_results"][:10] if o.get("url")]
    return urls, _extract_features(parsed)


def _compute_matrix(keywords, serp_urls, method) -> dict[str, dict[str, float]]:
    fn = jaccard if method == "jaccard" else percentage
    matrix: dict[str, dict[str, float]] = {k: {} for k in keywords}
    for i, k1 in enumerate(keywords):
        a = set(serp_urls.get(k1, []))
        matrix[k1][k1] = 1.0
        for k2 in keywords[i + 1:]:
            b = set(serp_urls.get(k2, []))
            score = fn(a, b)
            matrix[k1][k2] = score
            matrix[k2][k1] = score
    return matrix


def _compute_shared(keywords, serp_urls) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {k: {} for k in keywords}
    for i, k1 in enumerate(keywords):
        a = set(serp_urls.get(k1, []))
        out[k1][k1] = len(a)
        for k2 in keywords[i + 1:]:
            b = set(serp_urls.get(k2, []))
            n = shared_count(a, b)
            out[k1][k2] = n
            out[k2][k1] = n
    return out


def _serve_and_wait(*, state_path, keywords, volumes, result, domains, threshold) -> dict:
    """Start http.server, open browser, block until /save POST or timeout."""
    env = Environment(
        loader=FileSystemLoader(str(FRONTEND_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("cluster.html.j2")

    pkg_version = package_version()

    html = template.render(
        keywords=keywords,
        volumes=volumes,
        serps=result["serps"],
        serp_features=result["serp_features"],
        jaccard=result["matrix"],
        shared_count=result["shared_count_matrix"],
        initial_clusters=result["clusters"],
        ungrouped=result["ungrouped"],
        domains=domains,
        threshold=threshold,
        session_seconds=SESSION_SECONDS,
        brand=Brand.NAME,
        version=pkg_version,
        state_path=str(state_path),
    )

    saved_state: dict[str, Any] = {
        "clusters": result["clusters"],
        "ungrouped": result["ungrouped"],
        "threshold": threshold,
        "saved": False,
    }
    state_lock = threading.Lock()
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a, **kw): pass

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, "text/html", html.encode("utf-8"))
            elif self.path.startswith("/static/"):
                fname = self.path.split("/")[-1]
                fpath = FRONTEND_DIR / fname
                if fpath.exists() and fpath.is_file():
                    ctype = "text/css" if fname.endswith(".css") else "application/javascript"
                    self._send(200, ctype, fpath.read_bytes())
                else:
                    self._send(404, "text/plain", b"not found")
            else:
                self._send(404, "text/plain", b"not found")

        def do_POST(self):
            if self.path == "/save":
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                try:
                    data = json.loads(body.decode("utf-8"))
                    with state_lock:
                        saved_state["clusters"] = data.get("clusters", [])
                        saved_state["ungrouped"] = data.get("ungrouped", [])
                        saved_state["threshold"] = data.get("threshold", threshold)
                        saved_state["saved"] = True
                except Exception:
                    pass
                with state_lock:
                    payload = json.dumps(saved_state, ensure_ascii=False, default=str)
                state_path.write_text(payload)
                self._send(200, "text/plain", b"ok")
                threading.Thread(
                    target=lambda: (time.sleep(0.5), done.set()), daemon=True
                ).start()
            else:
                self._send(404, "text/plain", b"not found")

        def _send(self, status, ctype, body):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print(json.dumps({
        "server_port": port,
        "state_path": str(state_path),
        "status": "awaiting_user",
    }, ensure_ascii=False), file=sys.stderr)

    try:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    except Exception:
        pass

    timeout_ts = time.time() + SESSION_SECONDS + 5
    try:
        while not done.is_set() and time.time() < timeout_ts:
            done.wait(timeout=1.0)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()

    if not saved_state["saved"]:
        with state_lock:
            payload = json.dumps({**saved_state, "status": "no_changes"},
                                 ensure_ascii=False, default=str)
        state_path.write_text(payload)

    return saved_state


def _write_output_csv(path, state) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["keyword", "cluster_id", "is_primary", "volume"])
        for ci, c in enumerate(state["clusters"]):
            for kw in c["members"]:
                w.writerow([kw, ci + 1, kw == c["primary"], c.get("volume", 0)])
        for kw in state["ungrouped"]:
            w.writerow([kw, "", False, 0])
