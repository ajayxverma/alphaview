import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, MetaData, String, Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from alphaview_common.db import make_engine

SCHEMA = "integrations"
engine, SessionLocal = make_engine()


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


class Connection(Base):
    """A workspace's authenticated link to an external analytics tool."""

    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Owned by the identity service; no cross-schema FK.
    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)
    provider: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
