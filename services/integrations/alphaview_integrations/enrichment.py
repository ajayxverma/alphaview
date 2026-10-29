import asyncio
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphaview_common.security import decrypt_json
from alphaview_integrations.connectors.base import KeywordMetrics
from alphaview_integrations.connectors.registry import get_connector
from alphaview_integrations.models import Connection

_AVERAGED = {"trend_growth", "competition"}


async def enrich_keywords(
    db: AsyncSession, workspace_id: uuid.UUID, keywords: list[str]
) -> tuple[KeywordMetrics, list[str]]:
    """Fan out to every active connection in the workspace and merge normalized metrics."""
    conns = (
        await db.scalars(
            select(Connection).where(Connection.workspace_id == workspace_id, Connection.status == "active")
        )
    ).all()
    if not conns or not keywords:
        return {}, []

    async with httpx.AsyncClient(timeout=30) as client:

        async def call(conn: Connection) -> tuple[Connection, KeywordMetrics | None, str | None]:
            connector = get_connector(conn.provider)
            if connector is None or not connector.available():
                return conn, None, None
            try:
                creds = decrypt_json(conn.encrypted_credentials)
                return conn, await connector.enrich(client, creds, conn.config, keywords), None
            except Exception as exc:  # third-party failure must not break the whole run
                return conn, None, str(exc)[:500]

        results = await asyncio.gather(*(call(c) for c in conns))

    merged: KeywordMetrics = {}
    counts: dict[tuple[str, str], int] = {}
    used: list[str] = []
    for conn, data, err in results:
        conn.last_error = err
        if not data:
            continue
        used.append(conn.provider)
        for kw, metrics in data.items():
            bucket = merged.setdefault(kw, {})
            for name, value in metrics.items():
                if name not in bucket:
                    bucket[name] = value
                    counts[(kw, name)] = 1
                elif name in _AVERAGED:
                    n = counts[(kw, name)]
                    bucket[name] = (bucket[name] * n + value) / (n + 1)
                    counts[(kw, name)] = n + 1
                else:
                    bucket[name] = max(bucket[name], value)
    await db.commit()
    return merged, sorted(set(used))
