"""Integration tests for rank-check using rollback fixture + mocked client."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from seo_toolbox.commands.rank_check import run_rank_check
from seo_toolbox.db import SerpCache


@pytest.fixture
def keyword():
    return "test_kw_" + uuid.uuid4().hex[:8]


def _expires(days: int = 7) -> datetime:
    return datetime.now() + timedelta(days=days)


async def test_cache_hit_when_url_in_top_10(db_session, keyword):
    cached = SerpCache(
        keyword=keyword,
        location_code=2158,
        language_code="zh-TW",
        serp_data={
            "organic_results": [
                {
                    "url": "https://www.target.com/page",
                    "rank_group": 1,
                    "rank_absolute": 1,
                    "title": "T",
                    "domain": "target.com",
                },
                {
                    "url": "https://other.com/x",
                    "rank_group": 2,
                    "rank_absolute": 2,
                    "title": "O",
                    "domain": "other.com",
                },
            ],
            "ai_overview": None,
            "featured_snippet": None,
            "metadata": {"depth_fetched": 20},
        },
        fetched_at=datetime.now() - timedelta(seconds=120),
        expires_at=_expires(),
    )
    db_session.add(cached)
    await db_session.flush()

    mock_client = AsyncMock()
    result = await run_rank_check(
        keyword=keyword,
        target_url="https://www.target.com/page",
        session=db_session,
        client=mock_client,
    )
    assert result["organic_rank"] == 1
    assert result["cache"]["hit"] is True
    assert result["cost_usd"] == 0.0
    mock_client.fetch_serp.assert_not_called()
    # age_seconds should reflect the seeded fetched_at, not 0 (silent fallback bug)
    assert result["cache"]["age_seconds"] >= 100
    assert result["cache"]["age_seconds"] < 200


async def test_cache_miss_calls_api_and_writes(db_session, keyword):
    fake_response = {
        "keyword": keyword,
        "items": [
            {
                "type": "organic",
                "url": "https://target.com/page",
                "rank_group": 4,
                "rank_absolute": 9,
                "title": "T",
                "domain": "target.com",
            },
        ],
        "item_types": ["organic"],
        "total_results": 1000,
        "cost": 0.008,
    }
    mock_client = AsyncMock()
    mock_client.fetch_serp.return_value = fake_response

    result = await run_rank_check(
        keyword=keyword,
        target_url="https://target.com/page",
        session=db_session,
        client=mock_client,
    )
    assert result["organic_rank"] == 1  # only one organic in fake response
    assert result["cache"]["hit"] is False
    assert result["cost_usd"] == 0.008

    # Verify cache row was written
    res = await db_session.execute(select(SerpCache).where(SerpCache.keyword == keyword))
    row = res.scalar_one()
    assert row.serp_data["metadata"]["depth_fetched"] == 60


async def test_shallow_cache_refetches_when_url_missing(db_session, keyword):
    """Cluster wrote depth=20 cache without target URL — rank-check must refetch."""
    cached = SerpCache(
        keyword=keyword,
        location_code=2158,
        language_code="zh-TW",
        serp_data={
            "organic_results": [{"url": "https://other.com/x", "rank_group": 1}],
            "metadata": {"depth_fetched": 20},
        },
        fetched_at=datetime.now() - timedelta(seconds=120),
        expires_at=_expires(),
    )
    db_session.add(cached)
    await db_session.flush()

    fake_response = {
        "keyword": keyword,
        "items": [
            {
                "type": "organic",
                "url": "https://target.com/page",
                "rank_group": 30,
                "rank_absolute": 35,
                "title": "T",
                "domain": "target.com",
            },
        ],
        "item_types": ["organic"],
        "total_results": 5000,
        "cost": 0.009,
    }
    mock_client = AsyncMock()
    mock_client.fetch_serp.return_value = fake_response

    result = await run_rank_check(
        keyword=keyword,
        target_url="https://target.com/page",
        session=db_session,
        client=mock_client,
    )
    assert result["cache"]["hit"] is False
    mock_client.fetch_serp.assert_called_once()
    # Verify refetch upgraded the cache
    res = await db_session.execute(select(SerpCache).where(SerpCache.keyword == keyword))
    row = res.scalar_one()
    assert row.serp_data["metadata"]["depth_fetched"] == 60


async def test_finds_in_ai_overview(db_session, keyword):
    cached = SerpCache(
        keyword=keyword,
        location_code=2158,
        language_code="zh-TW",
        serp_data={
            "organic_results": [{"url": "https://other.com/x"}],
            "ai_overview": {
                "references": [{"url": "https://target.com/page", "title": "Cited"}],
            },
            "metadata": {"depth_fetched": 60},
        },
        fetched_at=datetime.now() - timedelta(seconds=120),
        expires_at=_expires(),
    )
    db_session.add(cached)
    await db_session.flush()

    result = await run_rank_check(
        keyword=keyword,
        target_url="https://target.com/page",
        session=db_session,
        client=AsyncMock(),
    )
    assert result["in_ai_overview"] is True
    assert result["organic_rank"] is None  # not in organic
    assert any(f["where"] == "ai_overview.reference" for f in result["findings"])


async def test_url_not_found_with_deep_cache_returns_null_rank(db_session, keyword):
    """If cached at depth=60 and URL absent, conclusively report not ranked (no refetch)."""
    cached = SerpCache(
        keyword=keyword,
        location_code=2158,
        language_code="zh-TW",
        serp_data={
            "organic_results": [{"url": f"https://site{i}.com"} for i in range(50)],
            "metadata": {"depth_fetched": 60},
        },
        fetched_at=datetime.now() - timedelta(seconds=120),
        expires_at=_expires(),
    )
    db_session.add(cached)
    await db_session.flush()

    mock_client = AsyncMock()
    result = await run_rank_check(
        keyword=keyword,
        target_url="https://target.com/page",
        session=db_session,
        client=mock_client,
    )
    assert result["organic_rank"] is None
    assert result["cache"]["hit"] is True
    mock_client.fetch_serp.assert_not_called()
