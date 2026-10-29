import uuid
from datetime import timedelta
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alphaview_common.auth import Principal, get_principal
from alphaview_common.security import create_token, decode_token, decrypt_json, encrypt_json
from alphaview_integrations.config import get_settings
from alphaview_integrations.connectors import google_oauth
from alphaview_integrations.connectors.base import Connector, ConnectorError, KeywordMetrics
from alphaview_integrations.connectors.registry import REGISTRY, get_connector
from alphaview_integrations.models import Connection, get_db
from alphaview_integrations.schemas import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionQueryIn,
    ConnectorOut,
    OAuthStartIn,
)

router = APIRouter(tags=["integrations"])


def _require_connector(provider: str, auth_type: str | None = None) -> Connector:
    connector = get_connector(provider)
    if connector is None or not connector.available():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or unavailable connector")
    if auth_type and connector.auth_type != auth_type:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{provider} uses {connector.auth_type} auth")
    return connector


def _clean_config(connector: Connector, config: dict[str, str]) -> dict[str, str]:
    allowed = {f.key: f for f in connector.config_fields}
    cleaned = {k: v.strip()[:300] for k, v in config.items() if k in allowed and v.strip()}
    missing = [f.label for f in allowed.values() if f.required and f.key not in cleaned]
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Missing config: {', '.join(missing)}")
    return cleaned


async def _get_connection(db: AsyncSession, principal: Principal, connection_id: uuid.UUID) -> Connection:
    conn = await db.get(Connection, connection_id)
    if conn is None or conn.workspace_id != principal.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    return conn


@router.get("/connectors", response_model=list[ConnectorOut])
async def list_connectors() -> list[ConnectorOut]:
    return [
        ConnectorOut(
            id=c.id,
            name=c.name,
            description=c.description,
            auth_type=c.auth_type,
            capabilities=[str(x) for x in c.capabilities],
            credential_fields=c.credential_fields,
            config_fields=c.config_fields,
            available=c.available(),
        )
        for c in REGISTRY.values()
    ]


@router.get("/connections", response_model=list[ConnectionOut])
async def list_connections(
    principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
) -> list[Connection]:
    rows = await db.scalars(
        select(Connection)
        .where(Connection.workspace_id == principal.workspace_id)
        .order_by(Connection.created_at.desc())
    )
    return list(rows)


@router.post("/connections", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: ConnectionCreate, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
) -> Connection:
    connector = _require_connector(body.provider, "api_key")
    config = _clean_config(connector, body.config)
    allowed = {f.key for f in connector.credential_fields}
    creds = {k: v.strip() for k, v in body.credentials.items() if k in allowed and v.strip()}
    if set(creds) != allowed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "All credential fields are required")

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            await connector.test(client, creds, config)
        except (ConnectorError, httpx.HTTPError) as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Connection test failed: {exc}") from exc

    conn = Connection(
        workspace_id=principal.workspace_id,
        provider=connector.id,
        label=body.label.strip(),
        config=config,
        encrypted_credentials=encrypt_json(creds),
    )
    db.add(conn)
    await db.commit()
    return conn


@router.post("/connections/oauth/{provider}/start")
async def oauth_start(
    provider: str, body: OAuthStartIn, principal: Principal = Depends(get_principal)
) -> dict[str, str]:
    connector = _require_connector(provider, "oauth2")
    config = _clean_config(connector, body.config)
    state = create_token(
        principal.user_id,
        purpose="oauth",
        ttl=timedelta(minutes=10),
        ws=str(principal.workspace_id),
        provider=provider,
        label=body.label.strip()[:120],
        config=config,
    )
    return {"authorization_url": google_oauth.authorization_url(state, connector.oauth_scopes)}


@router.get("/connections/oauth/callback", include_in_schema=False)
async def oauth_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    front = f"{get_settings().frontend_url}/integrations"

    def back(**params: str) -> RedirectResponse:
        return RedirectResponse(f"{front}?{urlencode(params)}", status_code=status.HTTP_303_SEE_OTHER)

    try:
        payload = decode_token(state, purpose="oauth")
    except jwt.PyJWTError:
        return back(error="Invalid or expired OAuth state")
    if error or not code:
        return back(error=error or "Authorization cancelled")

    connector = get_connector(payload["provider"])
    if connector is None:
        return back(error="Unknown connector")

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            creds = await google_oauth.exchange_code(client, code)
        except (ConnectorError, httpx.HTTPError) as exc:
            return back(error=str(exc)[:200])
        conn = Connection(
            workspace_id=uuid.UUID(payload["ws"]),
            provider=connector.id,
            label=payload["label"],
            config=payload.get("config", {}),
            encrypted_credentials=encrypt_json(creds),
        )
        try:
            await connector.test(client, creds, conn.config)
        except (ConnectorError, httpx.HTTPError) as exc:
            conn.status, conn.last_error = "error", str(exc)[:500]

    db.add(conn)
    await db.commit()
    return back(connected=connector.id)


@router.post("/connections/{connection_id}/test", response_model=ConnectionOut)
async def test_connection(
    connection_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
) -> Connection:
    conn = await _get_connection(db, principal, connection_id)
    connector = _require_connector(conn.provider)
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            await connector.test(client, decrypt_json(conn.encrypted_credentials), conn.config)
            conn.status, conn.last_error = "active", None
        except (ConnectorError, httpx.HTTPError) as exc:
            conn.status, conn.last_error = "error", str(exc)[:500]
    await db.commit()
    return conn


@router.post("/connections/{connection_id}/query")
async def query_connection(
    connection_id: uuid.UUID,
    body: ConnectionQueryIn,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> KeywordMetrics:
    conn = await _get_connection(db, principal, connection_id)
    connector = _require_connector(conn.provider)
    keywords = [k.strip()[:100] for k in body.keywords if k.strip()]
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            return await connector.enrich(client, decrypt_json(conn.encrypted_credentials), conn.config, keywords)
        except (ConnectorError, httpx.HTTPError) as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"{connector.name} error: {exc}") from exc


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
) -> None:
    conn = await _get_connection(db, principal, connection_id)
    await db.delete(conn)
    await db.commit()
