"""seo rank-check — find a target URL's position for a keyword.

Output: JSON to stdout by default. --pretty for human-readable.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seo_toolbox.cache import CacheDecision, decide_rank_check_cache_action
from seo_toolbox.config import load_config
from seo_toolbox.dataforseo import DataForSEOClient, parse_serp_items
from seo_toolbox.db import SerpCache, make_engine, make_session_factory
from seo_toolbox.registry import Market, SerpFetch
from seo_toolbox.url_utils import normalize_url

REQUIRED_DEPTH = SerpFetch.RANK_CHECK_DEPTH


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("rank-check", help="Find a URL's rank for a keyword")
    p.add_argument("keyword")
    p.add_argument("target_url")
    p.add_argument("--pretty", action="store_true")
    p.set_defaults(handler=_handler)


def _handler(args: argparse.Namespace) -> int:
    cfg = load_config()
    if not (cfg.database_url and cfg.dataforseo_login and cfg.dataforseo_password):
        print(json.dumps({
            "error": "config not set up — run `seo init --check`",
            "code": "config_invalid",
        }))
        return 1
    return asyncio.run(_async_main(cfg, args))


async def _async_main(cfg, args) -> int:
    engine = make_engine(cfg.database_url)
    factory = make_session_factory(engine)
    client = DataForSEOClient(
        cfg.dataforseo_login, cfg.dataforseo_password, sandbox=cfg.dataforseo_sandbox
    )
    try:
        async with factory() as session:
            result = await run_rank_check(
                keyword=args.keyword,
                target_url=args.target_url,
                session=session,
                client=client,
                location_code=cfg.location_code,
                language_code=cfg.language_code,
                ttl_days=cfg.serp_ttl_days,
            )
            await session.commit()
    finally:
        await engine.dispose()

    if args.pretty:
        _print_pretty(result)
    else:
        print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


async def run_rank_check(
    *,
    keyword: str,
    target_url: str,
    session: AsyncSession,
    client: Any,
    location_code: int = Market.LOCATION_CODE,
    language_code: str = Market.LANGUAGE_CODE,
    ttl_days: int = 7,
) -> dict[str, Any]:
    target_norm = normalize_url(target_url)

    # Lookup cache
    res = await session.execute(
        select(SerpCache).where(
            SerpCache.keyword == keyword,
            SerpCache.location_code == location_code,
            SerpCache.language_code == language_code,
        )
    )
    cached_row = res.scalar_one_or_none()
    cached_dict = None
    if cached_row:
        cached_dict = {
            "serp_data": cached_row.serp_data,
            "expires_at": cached_row.expires_at,
        }

    decision = decide_rank_check_cache_action(
        cached=cached_dict, target_url=target_url, required_depth=REQUIRED_DEPTH,
    )

    cost_usd = 0.0
    cache_hit = decision in (CacheDecision.HIT_FOUND, CacheDecision.HIT_NOT_RANKED)

    if not cache_hit:
        api = await client.fetch_serp(
            keyword=keyword, location_code=location_code,
            language_code=language_code, depth=REQUIRED_DEPTH,
        )
        cost_usd = api.get("cost", 0.0)
        parsed = parse_serp_items(api["items"])
        parsed["metadata"] = {"depth_fetched": REQUIRED_DEPTH}
        parsed["item_types"] = api.get("item_types", [])

        new_expires = datetime.now() + timedelta(days=ttl_days)
        now = datetime.now()
        if cached_row:
            cached_row.serp_data = parsed
            cached_row.total_results = api.get("total_results")
            cached_row.fetched_at = now
            cached_row.expires_at = new_expires
        else:
            cached_row = SerpCache(
                keyword=keyword,
                location_code=location_code,
                language_code=language_code,
                serp_data=parsed,
                total_results=api.get("total_results"),
                fetched_at=now,
                expires_at=new_expires,
            )
            session.add(cached_row)
        await session.flush()

    serp_data = cached_row.serp_data
    return _build_findings(
        keyword=keyword,
        target_url=target_url,
        target_norm=target_norm,
        serp_data=serp_data,
        cached_row=cached_row,
        cache_hit=cache_hit,
        cost_usd=cost_usd,
    )


def _build_findings(
    *, keyword, target_url, target_norm, serp_data, cached_row, cache_hit, cost_usd
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    # Organic
    organic = serp_data.get("organic_results", [])
    organic_rank = None
    organic_total = len(organic)
    for i, item in enumerate(organic, start=1):
        if normalize_url(item.get("url")) == target_norm:
            if organic_rank is None:
                organic_rank = i
            findings.append({
                "where": "organic",
                "rank": i,
                "rank_absolute": item.get("rank_absolute"),
                "title": item.get("title"),
                "url": item.get("url"),
            })

    # AI Overview
    in_ai_overview = False
    ai = serp_data.get("ai_overview")
    if ai:
        for ref in ai.get("references", []) or []:
            if normalize_url(ref.get("url")) == target_norm:
                in_ai_overview = True
                findings.append({
                    "where": "ai_overview.reference",
                    "title": ref.get("title"),
                    "url": ref.get("url"),
                })
        for sub in ai.get("items", []) or []:
            if normalize_url(sub.get("url")) == target_norm:
                in_ai_overview = True
                findings.append({
                    "where": "ai_overview.item",
                    "title": sub.get("title"),
                    "url": sub.get("url"),
                })

    # Featured snippet
    in_fs = False
    fs = serp_data.get("featured_snippet")
    if fs and normalize_url(fs.get("url")) == target_norm:
        in_fs = True
        findings.append({
            "where": "featured_snippet",
            "title": fs.get("title"),
            "url": fs.get("url"),
        })

    age = (datetime.now() - cached_row.fetched_at).total_seconds()

    return {
        "keyword": keyword,
        "target_url": target_url,
        "target_normalized": target_norm,
        "findings": findings,
        "organic_rank": organic_rank,
        "organic_total": organic_total,
        "in_ai_overview": in_ai_overview,
        "in_featured_snippet": in_fs,
        "cache": {
            "hit": cache_hit,
            "age_seconds": int(age),
            "fetched_at": cached_row.fetched_at.isoformat(),
        },
        "cost_usd": cost_usd,
    }


def _print_pretty(r: dict[str, Any]) -> None:
    print(f"Keyword: {r['keyword']}")
    print(f"Target:  {r['target_normalized']}")
    print(f"{'✓' if r['in_ai_overview'] else '✗'} AI Overview citation")
    print(f"{'✓' if r['in_featured_snippet'] else '✗'} Featured Snippet")
    if r["organic_rank"]:
        print(f"✓ Organic #{r['organic_rank']} (out of {r['organic_total']})")
    else:
        print(f"✗ Not in top {r['organic_total']} organic")
    age_min = r["cache"]["age_seconds"] // 60
    hit_str = "HIT" if r["cache"]["hit"] else "MISS"
    print(f"Cache: {hit_str} (age {age_min}m) | Cost: ${r['cost_usd']:.4f}")
