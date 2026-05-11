"""Unit tests for cache decision logic. No DB — operates on dicts."""

from datetime import UTC, datetime, timedelta

from seo_toolbox.cache import CacheDecision, decide_rank_check_cache_action


def _make_cache(*, depth: int, urls: list[str], expires_in_seconds: int = 3600):
    """Build a fake cached row dict. expires_in_seconds is from now (positive=fresh)."""
    return {
        "serp_data": {
            "organic_results": [{"url": u} for u in urls],
            "metadata": {"depth_fetched": depth},
        },
        "expires_at": datetime.now() + timedelta(seconds=expires_in_seconds),
    }


def test_url_in_top_10_returns_hit_regardless_of_depth():
    cache = _make_cache(depth=20, urls=["a.com/1", "a.com/2", "target.com/page"])
    decision = decide_rank_check_cache_action(
        cached=cache, target_url="target.com/page", required_depth=60
    )
    assert decision == CacheDecision.HIT_FOUND


def test_url_not_found_with_sufficient_depth_returns_conclusive_miss():
    cache = _make_cache(depth=60, urls=[f"site{i}.com" for i in range(50)])
    decision = decide_rank_check_cache_action(
        cached=cache, target_url="target.com/page", required_depth=60
    )
    assert decision == CacheDecision.HIT_NOT_RANKED


def test_url_not_found_with_shallow_depth_returns_refetch():
    cache = _make_cache(depth=20, urls=[f"site{i}.com" for i in range(10)])
    decision = decide_rank_check_cache_action(
        cached=cache, target_url="target.com/page", required_depth=60
    )
    assert decision == CacheDecision.REFETCH


def test_expired_cache_returns_refetch():
    cache = _make_cache(
        depth=60,
        urls=["target.com/page"],
        expires_in_seconds=-60,  # expired 60s ago
    )
    decision = decide_rank_check_cache_action(
        cached=cache, target_url="target.com/page", required_depth=60
    )
    assert decision == CacheDecision.REFETCH


def test_no_cache_returns_refetch():
    decision = decide_rank_check_cache_action(
        cached=None, target_url="target.com/page", required_depth=60
    )
    assert decision == CacheDecision.REFETCH


def test_legacy_record_no_metadata_treated_as_depth_20():
    cache = {
        "serp_data": {"organic_results": [{"url": "other.com/x"}]},  # no metadata
        "expires_at": datetime.now() + timedelta(hours=1),
    }
    decision = decide_rank_check_cache_action(
        cached=cache, target_url="target.com/page", required_depth=60
    )
    # depth=20 (legacy default), URL not in top-10 → refetch
    assert decision == CacheDecision.REFETCH


def test_url_normalization_applied_to_target_and_cached_urls():
    """`https://www.target.com/page/` should match cached `target.com/page` and vice versa."""
    cache = _make_cache(depth=20, urls=["https://target.com/page"])
    # Same URL with www prefix and trailing slash
    decision = decide_rank_check_cache_action(
        cached=cache, target_url="https://www.target.com/page/", required_depth=60
    )
    assert decision == CacheDecision.HIT_FOUND


def test_handles_timezone_aware_expires_at():
    """If a caller passes tz-aware datetime, the function should not crash."""
    cache = {
        "serp_data": {
            "organic_results": [{"url": "target.com/page"}],
            "metadata": {"depth_fetched": 60},
        },
        "expires_at": datetime.now(UTC) + timedelta(hours=1),  # tz-aware future
    }
    decision = decide_rank_check_cache_action(
        cached=cache, target_url="target.com/page", required_depth=60
    )
    assert decision == CacheDecision.HIT_FOUND
