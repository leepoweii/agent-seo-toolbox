"""Integration test fixtures — rollback per test against long-lived Neon test branch.

Reads .env.test from repo root for DATABASE_URL.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from seo_toolbox.db import make_engine

# Load .env.test from repo root (works regardless of pytest's cwd)
load_dotenv(Path(__file__).parent.parent.parent / ".env.test")


@pytest_asyncio.fixture
async def engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        import pytest

        pytest.skip("DATABASE_URL not set (no .env.test)")
    eng = make_engine(url)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Rollback-on-teardown fixture.

    Each test gets its own connection and transaction. All writes are rolled
    back at teardown so tests don't pollute the long-lived test branch.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
