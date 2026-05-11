import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from seo_toolbox.db import SerpCache


def _expires() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None) + timedelta(days=7)


async def test_insert_and_read(db_session):
    row = SerpCache(
        keyword="test_kw_" + uuid.uuid4().hex[:8],
        location_code=2158,
        language_code="zh-TW",
        serp_data={"organic_results": [], "metadata": {"depth_fetched": 20}},
        total_results=12345,
        expires_at=_expires(),
    )
    db_session.add(row)
    await db_session.flush()

    result = await db_session.execute(select(SerpCache).where(SerpCache.keyword == row.keyword))
    fetched = result.scalar_one()
    assert fetched.location_code == 2158
    assert fetched.depth_fetched == 20
    assert fetched.total_results == 12345


async def test_depth_fetched_legacy_default(db_session):
    """Records without metadata.depth_fetched default to 20."""
    row = SerpCache(
        keyword="legacy_kw_" + uuid.uuid4().hex[:8],
        location_code=2158,
        language_code="zh-TW",
        serp_data={"organic_results": []},  # no metadata
        expires_at=_expires(),
    )
    db_session.add(row)
    await db_session.flush()
    assert row.depth_fetched == 20


async def test_api_cost_defaults_to_none(db_session):
    """api_cost column defaults to None when not set."""
    row = SerpCache(
        keyword="apicost_kw_" + uuid.uuid4().hex[:8],
        location_code=2158,
        language_code="zh-TW",
        serp_data={"organic_results": []},
        # api_cost intentionally not set
        expires_at=_expires(),
    )
    db_session.add(row)
    await db_session.flush()
    await db_session.refresh(row)
    assert row.api_cost is None


async def test_unique_constraint(db_session):
    keyword = "unique_kw_" + uuid.uuid4().hex[:8]
    row1 = SerpCache(
        keyword=keyword,
        location_code=2158,
        language_code="zh-TW",
        serp_data={"organic_results": []},
        expires_at=_expires(),
    )
    db_session.add(row1)
    await db_session.flush()

    row2 = SerpCache(
        keyword=keyword,
        location_code=2158,
        language_code="zh-TW",
        serp_data={"organic_results": []},
        expires_at=_expires(),
    )
    db_session.add(row2)
    try:
        await db_session.flush()
        raise AssertionError("expected IntegrityError")
    except IntegrityError:
        await db_session.rollback()
