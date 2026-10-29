from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from alphaview_common.settings import get_common_settings


def make_engine() -> tuple[AsyncEngine, async_sessionmaker]:
    engine = create_async_engine(
        get_common_settings().database_url, pool_size=10, max_overflow=20, pool_pre_ping=True
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def init_schema(engine: AsyncEngine, base: type[DeclarativeBase], schema: str) -> None:
    """Each service owns exactly one Postgres schema."""
    async with engine.begin() as conn:
        # Serialize DDL across replicas/uvicorn workers starting at the same time.
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:s))"), {"s": schema})
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.run_sync(base.metadata.create_all)
