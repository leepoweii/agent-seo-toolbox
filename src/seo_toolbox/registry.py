"""Single source of truth for cross-module constants.

Anywhere in the codebase that needs a "magic" value (default fetch depth,
TTL, market code, brand name, color token, etc.), it should be defined
here and imported — not duplicated. New pages and tools should pull from
this registry so they share defaults.

Frontend:
- Color tokens live in CSS `:root` (cluster.css) for runtime CSS-var
  reference. The hex values are mirrored under `Colors` here so backend
  templates / JSON payloads stay in sync. If you change a color, update
  BOTH places.
- Sidebar width same story: CSS `--sidebar-w` is the live value;
  `UI.SIDEBAR_WIDTH_PX` is the mirror.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version


# ----------------------------------------------------------------------
# Brand / metadata
# ----------------------------------------------------------------------

class Brand:
    NAME = "AGENT-SEO-TOOLBOX"


def package_version(default: str = "0.0.0") -> str:
    """Resolve installed package version. Returns default if not installed."""
    try:
        return _pkg_version("agent-seo-toolbox")
    except PackageNotFoundError:
        return default


# ----------------------------------------------------------------------
# Market / locale defaults
# ----------------------------------------------------------------------

class Market:
    """Defaults for SERP fetches. Override per-call when needed."""
    LOCATION_CODE = 2158       # Taiwan (DataForSEO codes)
    LANGUAGE_CODE = "zh-TW"
    DEVICE = "mobile"
    OS = "ios"


# ----------------------------------------------------------------------
# SERP fetch depths
# ----------------------------------------------------------------------

class SerpFetch:
    CLUSTER_DEPTH = 20        # depth fetched for `seo cluster`
    RANK_CHECK_DEPTH = 60     # depth fetched for `seo rank-check`


# ----------------------------------------------------------------------
# Cache TTLs
# ----------------------------------------------------------------------

class Cache:
    SERP_TTL_DAYS = 7          # serp_cache rows
    EXPANSION_TTL_DAYS = 30    # keyword expansion (long-lived)
    VOLUME_TTL_DAYS = 30       # planned: volume_cache (see docs/TODO.md)


# ----------------------------------------------------------------------
# Cluster command defaults
# ----------------------------------------------------------------------

class Cluster:
    """`seo cluster` defaults. Threshold + method match industry convention.

    threshold = 0.30 with method = percentage means "≥ 3 of 10 SERP URLs shared"
    — this is the SE Ranking / Keyword Insights default.
    """
    DEFAULT_THRESHOLD = 0.30
    DEFAULT_METHOD = "percentage"   # alt: "jaccard" (research)
    SESSION_SECONDS = 30 * 60       # browser session before timeout


# ----------------------------------------------------------------------
# UI tokens — mirror of CSS values in cluster.css
# ----------------------------------------------------------------------

class UI:
    SIDEBAR_WIDTH_PX = 390  # CSS --sidebar-w


class Colors:
    """Hex strings — kept in sync with `:root` in frontend/cluster.css.
    Used when a backend payload needs to know the color (e.g. legend
    rendered server-side, or a non-HTML output channel)."""
    OWN = "#0EA472"          # green
    COMPETITOR = "#E94B7D"   # pink (brand)
    AUTHORITY = "#F59E0B"    # amber
    WARN = "#D97706"
    DANGER = "#DC2626"


__all__ = [
    "Brand", "Market", "SerpFetch", "Cache", "Cluster", "UI", "Colors",
    "package_version",
]
