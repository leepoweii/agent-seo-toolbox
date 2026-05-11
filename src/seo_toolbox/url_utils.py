"""URL normalization for SERP comparison.

Mirrors apps/web-v2/src/lib/grouping.ts in simple-seo-tools so cached
URLs match across both projects.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse

TRACKING_PARAMS = frozenset({
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "source",
})


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url
    if not parsed.netloc:
        return url

    host = parsed.netloc.lower().removeprefix("www.")
    # Note: ports (e.g., :8080) and userinfo (user:pass@) are retained as-is.
    # Real SERP URLs don't contain them; if they appear they're treated as part of host identity.
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

    pairs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    pairs.sort(key=lambda kv: kv[0])
    query = urlencode(pairs)

    base = f"{host}{path}"
    return f"{base}?{query}" if query else base
