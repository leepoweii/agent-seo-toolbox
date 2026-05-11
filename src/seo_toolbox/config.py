"""Layered configuration loading.

Lookup chain (first match wins):
  1. Explicit overrides (CLI flag mapped to dict)
  2. Project TOML: ./agent-seo-toolbox.toml
  3. Global TOML: $XDG_CONFIG_HOME/agent-seo-toolbox/config.toml
  4. Built-in defaults
Secrets always loaded from $XDG_CONFIG_HOME/agent-seo-toolbox/.env (or env vars).
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from seo_toolbox.registry import Cache, Cluster, Market


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "agent-seo-toolbox"
    return Path.home() / ".config" / "agent-seo-toolbox"


@dataclass
class Config:
    # Secrets (from .env)
    database_url: str = ""
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    dataforseo_sandbox: bool = False

    # Domains (from config.toml)
    own_domain: str = ""
    competitor_domains: list[str] = field(default_factory=list)
    authority_tlds: list[str] = field(default_factory=lambda: [".gov", ".edu", ".org"])

    # Defaults — sourced from registry.py
    location_code: int = Market.LOCATION_CODE
    language_code: str = Market.LANGUAGE_CODE
    device: str = Market.DEVICE
    os: str = Market.OS
    similarity_method: str = Cluster.DEFAULT_METHOD
    cluster_threshold: float = Cluster.DEFAULT_THRESHOLD

    # Cache
    serp_ttl_days: int = Cache.SERP_TTL_DAYS
    expansion_ttl_days: int = Cache.EXPANSION_TTL_DAYS


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _apply_toml(cfg: Config, data: dict) -> None:
    domains = data.get("domains", {})
    if "own" in domains:
        cfg.own_domain = domains["own"]
    if "competitors" in domains:
        cfg.competitor_domains = list(domains["competitors"])
    if "authority_tlds" in domains:
        cfg.authority_tlds = list(domains["authority_tlds"])

    defaults = data.get("defaults", {})
    for key in ("location_code", "language_code", "device", "os",
                "similarity_method", "cluster_threshold"):
        if key in defaults:
            setattr(cfg, key, defaults[key])

    cache = data.get("cache", {})
    if "serp_ttl_days" in cache:
        cfg.serp_ttl_days = cache["serp_ttl_days"]
    if "expansion_ttl_days" in cache:
        cfg.expansion_ttl_days = cache["expansion_ttl_days"]


def load_config(overrides: dict | None = None) -> Config:
    cfg = Config()

    # Layer 3: global TOML
    global_dir = _config_dir()
    _apply_toml(cfg, _load_toml(global_dir / "config.toml"))

    # Layer 2: project TOML
    project_path = Path.cwd() / "agent-seo-toolbox.toml"
    _apply_toml(cfg, _load_toml(project_path))

    # Layer 1: explicit overrides
    if overrides:
        for k, v in overrides.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)

    # Secrets: read .env file values then OS env vars (env wins).
    # Use dotenv_values to avoid mutating os.environ (test isolation).
    env_path = global_dir / ".env"
    file_secrets = dotenv_values(env_path) if env_path.exists() else {}

    def _resolve(key: str, current: str) -> str:
        return os.environ.get(key) or file_secrets.get(key) or current

    cfg.database_url = _resolve("DATABASE_URL", cfg.database_url)
    cfg.dataforseo_login = _resolve("DATAFORSEO_LOGIN", cfg.dataforseo_login)
    cfg.dataforseo_password = _resolve("DATAFORSEO_PASSWORD", cfg.dataforseo_password)
    sandbox_raw = _resolve("DATAFORSEO_SANDBOX", "")
    cfg.dataforseo_sandbox = sandbox_raw.lower() in ("true", "1", "yes", "on")

    return cfg
