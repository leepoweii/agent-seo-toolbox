"""seo init — write ~/.config/agent-seo-toolbox/config.toml.

Credentials (DATABASE_URL, DATAFORSEO_LOGIN/PASSWORD) are NOT written here —
they must be added manually to ~/.config/agent-seo-toolbox/.env to avoid
exposing secrets in command-line transcripts. Use `seo init --check` to verify
they're loadable.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import tomli_w

from seo_toolbox.config import _config_dir


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "init",
        help="Configure DataForSEO + Neon credentials and preferences",
    )
    p.add_argument("--own-domain", default=None)
    p.add_argument("--competitors", default=None,
                   help="Comma-separated list, e.g. 'a.com,b.com'")
    p.add_argument("--non-interactive", action="store_true")
    p.add_argument("--check", action="store_true",
                   help="Validate current config and connectivity instead of writing")
    p.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    cfg_dir = _config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)

    if args.check:
        return _run_check(cfg_dir)

    if args.non_interactive:
        own = args.own_domain or ""
        competitors = [s.strip() for s in (args.competitors or "").split(",") if s.strip()]
    else:
        if not sys.stdin.isatty():
            print(json.dumps({
                "error": "stdin is not a TTY; use --non-interactive with flags",
                "code": "no_tty",
            }))
            return 1
        try:
            import questionary
        except ImportError:
            print(json.dumps({"error": "questionary not installed", "code": "missing_dep"}))
            return 1
        own = questionary.text("Own domain (e.g. my-site.com.tw):").ask() or ""
        competitors_raw = questionary.text("Competitor domains (comma-separated):").ask() or ""
        competitors = [s.strip() for s in competitors_raw.split(",") if s.strip()]

    cfg_path = cfg_dir / "config.toml"
    existing: dict = {}
    if cfg_path.exists():
        import tomllib
        with open(cfg_path, "rb") as f:
            existing = tomllib.load(f)

    existing.setdefault("domains", {})
    if own:
        existing["domains"]["own"] = own
    if competitors:
        existing["domains"]["competitors"] = competitors

    with open(cfg_path, "wb") as f:
        tomli_w.dump(existing, f)

    saved = []
    if own:
        saved.append("domains.own")
    if competitors:
        saved.append("domains.competitors")

    print(json.dumps({"config_path": str(cfg_path), "saved_keys": saved}))
    return 0


def _run_check(cfg_dir: Path) -> int:
    """Validate config file present + DB reachable + DataForSEO auth ok."""
    from seo_toolbox.config import load_config

    cfg = load_config()
    config_valid = bool(cfg.database_url and cfg.dataforseo_login and cfg.dataforseo_password)

    db_ok = False
    if cfg.database_url:
        async def _ping_db():
            from sqlalchemy import text

            from seo_toolbox.db import make_engine
            eng = make_engine(cfg.database_url)
            try:
                async with eng.connect() as c:
                    await c.execute(text("SELECT 1"))
                return True
            except Exception:
                return False
            finally:
                await eng.dispose()
        db_ok = asyncio.run(_ping_db())

    auth_ok = "skip"
    if cfg.dataforseo_login and cfg.dataforseo_password:
        async def _ping_auth():
            from seo_toolbox.dataforseo import DataForSEOClient
            client = DataForSEOClient(cfg.dataforseo_login, cfg.dataforseo_password, sandbox=True)
            try:
                await client.fetch_serp(
                    keyword="test", location_code=2158, language_code="zh-TW", depth=10
                )
                return "ok"
            except Exception as e:
                return f"error: {e.__class__.__name__}"
        auth_ok = asyncio.run(_ping_auth())

    print(json.dumps({
        "config_valid": config_valid,
        "db_reachable": db_ok,
        "dataforseo_auth": auth_ok,
    }))
    return 0 if (config_valid and db_ok) else 1
