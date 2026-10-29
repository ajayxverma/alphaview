import enum
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, MetaData, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from alphaview_common.db import make_engine

SCHEMA = "discovery"
engine, SessionLocal = make_engine()


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _now() -> datetime:
    return datetime.now(UTC)


class RunStatus(enum.StrEnum):
    queued = "queued"
    crawling = "crawling"
    analyzing = "analyzing"
    enriching = "enriching"
    synthesizing = "synthesizing"
    completed = "completed"
    failed = "failed"


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # workspace_id / created_by are owned by the identity service; no cross-schema FKs.
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    query: Mapped[str] = mapped_column(String(300))
    sources: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default=RunStatus.queued.value)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opportunities: Mapped[list["Opportunity"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="desc(Opportunity.gap_score)"
    )


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discovery_runs.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    cluster_label: Mapped[str] = mapped_column(String(200))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    gap_score: Mapped[float] = mapped_column(Float, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    strategy: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped[DiscoveryRun] = relationship(back_populates="opportunities")
