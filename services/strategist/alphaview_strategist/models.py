import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, MetaData, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from alphaview_common.db import make_engine

SCHEMA = "strategist"
engine, SessionLocal = make_engine()


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


class AICredential(Base):
    """A workspace's key for one LLM provider; the default one is used for synthesis."""

    __tablename__ = "ai_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    provider: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(200))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
