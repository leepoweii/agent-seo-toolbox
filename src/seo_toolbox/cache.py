"""Depth-aware cache decision logic for rank-check.

The serp_cache table stores absolute `expires_at` (not relative TTL), so freshness
is just `now() < expires_at`. See docs for the decision tree.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from seo_toolbox.url_utils import normalize_url


class CacheDecision(Enum):
    HIT_FOUND = "hit_found"            # URL in cached organic — use this
    HIT_NOT_RANKED = "hit_not_ranked"  # depth sufficient & URL absent — conclusive
    REFETCH = "refetch"                # cache stale, missing, or shallow & URL absent


def _depth_from_serp_data(serp_data: dict[str, Any]) -> int:
    """Returns metadata.depth_fetched if present, else 20 (legacy default)."""
    return (serp_data or {}).get("metadata", {}).get("depth_fetched", 20)


def _is_fresh(expires_at: datetime) -> bool:
    """True if cache hasn't expired yet.

    The serp_cache.expires_at column is naive (timezone=False). If a caller passes
    a tz-aware datetime, convert to naive local time to keep the comparison valid
    rather than raising TypeError.
    """
    if expires_at.tzinfo is not None:
        # Convert tz-aware to naive local time to match datetime.now()
        expires_at = expires_at.astimezone().replace(tzinfo=None)
    return datetime.now() < expires_at


def decide_rank_check_cache_action(
    *,
    cached: dict[str, Any] | None,
    target_url: str,
    required_depth: int,
) -> CacheDecision:
    """Decide cache action for rank-check.

    Args:
        cached: dict with keys `serp_data` (dict) and `expires_at` (datetime),
                or None if no cache row exists.
        target_url: the URL we're looking for in the SERP.
        required_depth: minimum depth_fetched for a "not ranked" decision to be conclusive.

    Returns one of:
        HIT_FOUND       — URL is in cached organic results, return rank from cache.
        HIT_NOT_RANKED  — cached depth >= required_depth and URL absent, return null rank.
        REFETCH         — cache missing, expired, or insufficient depth + URL absent.
    """
    if not cached:
        return CacheDecision.REFETCH
    if not _is_fresh(cached["expires_at"]):
        return CacheDecision.REFETCH

    serp_data = cached.get("serp_data") or {}
    target_norm = normalize_url(target_url)
    organic = serp_data.get("organic_results", [])
    cached_urls = {normalize_url(o.get("url")) for o in organic}

    if target_norm in cached_urls:
        return CacheDecision.HIT_FOUND

    cached_depth = _depth_from_serp_data(serp_data)
    if cached_depth >= required_depth:
        return CacheDecision.HIT_NOT_RANKED

    return CacheDecision.REFETCH
