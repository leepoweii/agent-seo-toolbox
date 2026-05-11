"""SQLAlchemy 2 async session and ORM models.

Reuses the existing simple-seo-tools serp_cache table (no migration).
Schema reference: simple-seo-tools/stages/expansion/src/expansion/models.py
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SerpCache(Base):
    """Mirrors the serp_cache table created by simple-seo-tools migrations.

    Schema source:
        simple-seo-tools/stages/expansion/alembic/versions/
        328c3db0a8dc_create_all_kr_and_expansion_tables.py
    """

    __tablename__ = "serp_cache"
    __table_args__ = (
        UniqueConstraint("keyword", "location_code", "language_code",
                         name="uq_serp_cache_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    location_code: Mapped[int] = mapped_column(Integer, nullable=False)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    serp_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    total_results: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    api_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False
    )

    @property
    def depth_fetched(self) -> int:
        """Returns metadata.depth_fetched if present, else assumes 20 (legacy)."""
        return (self.serp_data or {}).get("metadata", {}).get("depth_fetched", 20)


def make_engine(database_url: str):
    # Convert postgresql://... to postgresql+asyncpg://...
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg doesn't accept channel_binding/sslmode in URL — strip if present
    if "?" in database_url:
        base, query = database_url.split("?", 1)
        params = [p for p in query.split("&")
                  if not p.startswith(("sslmode=", "channel_binding="))]
        database_url = base + ("?" + "&".join(params) if params else "")
    return create_async_engine(database_url, pool_pre_ping=True)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
