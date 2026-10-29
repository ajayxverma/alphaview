"""Shared ClickHouse event store. The crawler writes `signals`; other services only read it."""

import uuid

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

from alphaview_common.settings import get_common_settings
from alphaview_common.signals import Signal

_client: AsyncClient | None = None

SIGNAL_COLUMNS = [
    "run_id", "id", "source", "external_id", "url", "title", "text",
    "created_at", "engagement", "comments", "answered",
]

SIGNALS_DDL = """
CREATE TABLE IF NOT EXISTS signals (
    run_id UUID,
    id String,
    source LowCardinality(String),
    external_id String,
    url String,
    title String,
    text String,
    created_at DateTime('UTC'),
    engagement Int32,
    comments Int32,
    answered Nullable(UInt8),
    ingested_at DateTime('UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(ingested_at)
ORDER BY (run_id, id)
TTL ingested_at + INTERVAL 180 DAY
"""


async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        s = get_common_settings()
        bootstrap = await clickhouse_connect.get_async_client(
            host=s.clickhouse_host, port=s.clickhouse_port, username=s.clickhouse_user, password=s.clickhouse_password
        )
        await bootstrap.command(f"CREATE DATABASE IF NOT EXISTS {s.clickhouse_database}")
        _client = await clickhouse_connect.get_async_client(
            host=s.clickhouse_host,
            port=s.clickhouse_port,
            username=s.clickhouse_user,
            password=s.clickhouse_password,
            database=s.clickhouse_database,
        )
    return _client


async def fetch_signals(run_id: uuid.UUID) -> list[Signal]:
    client = await get_client()
    result = await client.query(
        f"SELECT {', '.join(SIGNAL_COLUMNS[2:])} FROM signals FINAL WHERE run_id = {{run_id:UUID}}",
        parameters={"run_id": str(run_id)},
    )
    return [
        Signal(
            source=source, external_id=ext_id, url=url, title=title, text=text, created_at=created,
            engagement=eng, comments=comments, answered=None if answered is None else bool(answered),
        )
        for source, ext_id, url, title, text, created, eng, comments, answered in result.result_rows
    ]
