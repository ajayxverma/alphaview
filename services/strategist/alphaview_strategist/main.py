import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
import litellm
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from alphaview_common import ratelimit
from alphaview_common.auth import Principal, get_principal
from alphaview_common.db import init_schema
from alphaview_common.netguard import UnsafeEndpointError
from alphaview_common.security import encrypt_json
from alphaview_common.web import create_app
from alphaview_strategist.config import get_settings
from alphaview_strategist.credentials import kwargs_for
from alphaview_strategist.models import SCHEMA, AICredential, Base, engine, get_db
from alphaview_strategist.providers import MODEL_LISTING, PROVIDERS, FieldSpec, ProviderSpec, call_kwargs, list_models


class ProviderOut(BaseModel):
    id: str
    name: str
    default_model: str
    models: list[str]
    can_list_models: bool
    docs_url: str
    credential_fields: list[FieldSpec]
    config_fields: list[FieldSpec]


class ModelListIn(BaseModel):
    credentials: dict[str, str] = Field(default_factory=dict)
    config: dict[str, str] = Field(default_factory=dict)


class AICredentialCreate(BaseModel):
    provider: str
    label: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=200)
    credentials: dict[str, str] = Field(default_factory=dict)
    config: dict[str, str] = Field(default_factory=dict)
    make_default: bool = True


class AICredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider: str
    label: str
    model: str
    config: dict[str, Any]
    is_default: bool
    status: str
    last_error: str | None
    created_at: datetime


@asynccontextmanager
async def lifespan(_app):
    await init_schema(engine, Base, SCHEMA)
    yield


app = create_app("strategist", lifespan)


def _clean(fields: tuple[FieldSpec, ...], values: dict[str, str], what: str) -> dict[str, str]:
    allowed = {f.key: f for f in fields}
    cleaned = {k: v.strip()[:2000] for k, v in values.items() if k in allowed and v.strip()}
    missing = [f.label for f in allowed.values() if f.required and f.key not in cleaned]
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Missing {what}: {', '.join(missing)}")
    return cleaned


async def _probe(kwargs: dict, secrets: dict[str, str]) -> str | None:
    """Tiny completion to verify the key/model; returns a redacted error or None."""
    try:
        await litellm.acompletion(
            **kwargs, messages=[{"role": "user", "content": "Reply with OK"}], max_tokens=5, timeout=30,
        )
        return None
    except Exception as exc:  # provider SDK errors vary widely
        message = f"{type(exc).__name__}: {exc}"
        for value in secrets.values():
            if value:
                message = message.replace(value, "***")
        if "NotFound" in message or "model_not_found" in message or "does not exist" in message:
            message = "Model not available for this key. Use 'Load models' to pick one you have access to. " + message
        return message[:500]


async def _get(db: AsyncSession, principal: Principal, cred_id: uuid.UUID) -> AICredential:
    cred = await db.get(AICredential, cred_id)
    if cred is None or cred.workspace_id != principal.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI provider not found")
    return cred


@app.get("/ai-providers", response_model=list[ProviderOut], tags=["ai"])
async def list_providers() -> list[ProviderOut]:
    return [
        ProviderOut(
            id=p.id, name=p.name, default_model=p.default_model, models=list(p.models),
            can_list_models=p.id in MODEL_LISTING, docs_url=p.docs_url,
            credential_fields=list(p.credential_fields), config_fields=list(p.config_fields),
        )
        for p in PROVIDERS.values()
    ]


@app.post("/ai-providers/{provider_id}/models", tags=["ai"])
async def provider_models(
    provider_id: str, body: ModelListIn, principal: Principal = Depends(get_principal)
) -> dict[str, list[str]]:
    """List the models the supplied (unsaved) key can use, so users pick a valid one before saving."""
    spec = PROVIDERS.get(provider_id)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown AI provider")
    await ratelimit.enforce(f"ai-models:{principal.workspace_id}", limit=60, window_seconds=3600)
    creds = {k: v.strip() for k, v in body.credentials.items() if k == "api_key" and v.strip()}
    config = {k: v.strip() for k, v in body.config.items() if k == "api_base" and v.strip()}
    if any(f.required and f.key not in creds for f in spec.credential_fields):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter your API key first")
    try:
        async with httpx.AsyncClient() as client:
            models = await list_models(client, spec, creds, config, get_settings().allow_private_llm_endpoints)
    except (UnsafeEndpointError, ValueError, PermissionError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not reach {spec.name}: {type(exc).__name__}") from exc
    if not models:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No chat models are available for this key")
    return {"models": models}


@app.get("/ai-credentials", response_model=list[AICredentialOut], tags=["ai"])
async def list_credentials(principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(AICredential)
        .where(AICredential.workspace_id == principal.workspace_id)
        .order_by(AICredential.is_default.desc(), AICredential.created_at.desc())
    )
    return list(rows)


@app.post("/ai-credentials", response_model=AICredentialOut, status_code=status.HTTP_201_CREATED, tags=["ai"])
async def create_credential(
    body: AICredentialCreate, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
) -> AICredential:
    spec: ProviderSpec | None = PROVIDERS.get(body.provider)
    if spec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown AI provider")
    await ratelimit.enforce(f"ai-test:{principal.workspace_id}", limit=30, window_seconds=3600)

    creds = _clean(spec.credential_fields, body.credentials, "credentials")
    config = _clean(spec.config_fields, body.config, "settings")
    model = body.model.strip()
    try:
        kwargs = await call_kwargs(spec, model, creds, config, get_settings().allow_private_llm_endpoints)
    except UnsafeEndpointError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    error = await _probe(kwargs, creds)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Connection test failed - {error}")

    has_default = await db.scalar(
        select(AICredential.id).where(
            AICredential.workspace_id == principal.workspace_id, AICredential.is_default.is_(True)
        )
    )
    make_default = body.make_default or has_default is None
    if make_default:
        await db.execute(
            update(AICredential).where(AICredential.workspace_id == principal.workspace_id).values(is_default=False)
        )
    cred = AICredential(
        workspace_id=principal.workspace_id,
        provider=spec.id,
        label=body.label.strip(),
        model=model,
        config=config,
        encrypted_credentials=encrypt_json(creds),
        is_default=make_default,
    )
    db.add(cred)
    await db.commit()
    return cred


@app.post("/ai-credentials/{cred_id}/default", response_model=AICredentialOut, tags=["ai"])
async def set_default(
    cred_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
) -> AICredential:
    cred = await _get(db, principal, cred_id)
    await db.execute(
        update(AICredential).where(AICredential.workspace_id == principal.workspace_id).values(is_default=False)
    )
    cred.is_default = True
    await db.commit()
    return cred


@app.post("/ai-credentials/{cred_id}/test", response_model=AICredentialOut, tags=["ai"])
async def test_credential(
    cred_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
) -> AICredential:
    cred = await _get(db, principal, cred_id)
    await ratelimit.enforce(f"ai-test:{principal.workspace_id}", limit=30, window_seconds=3600)
    try:
        kwargs = await kwargs_for(cred)
        error = await _probe(kwargs, {"api_key": kwargs.get("api_key", "")})
    except UnsafeEndpointError as exc:
        error = str(exc)
    cred.status, cred.last_error = ("error", error) if error else ("active", None)
    await db.commit()
    return cred


@app.delete("/ai-credentials/{cred_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["ai"])
async def delete_credential(
    cred_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
) -> None:
    cred = await _get(db, principal, cred_id)
    was_default = cred.is_default
    await db.delete(cred)
    await db.flush()
    if was_default:
        replacement = await db.scalar(
            select(AICredential)
            .where(AICredential.workspace_id == principal.workspace_id)
            .order_by(AICredential.created_at.desc())
            .limit(1)
        )
        if replacement is not None:
            replacement.is_default = True
    await db.commit()
