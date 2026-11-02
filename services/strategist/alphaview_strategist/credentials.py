import uuid

from sqlalchemy import select

from alphaview_common.security import decrypt_json
from alphaview_strategist.agent import server_default_llm
from alphaview_strategist.config import get_settings
from alphaview_strategist.models import AICredential, SessionLocal
from alphaview_strategist.providers import PROVIDERS, call_kwargs


async def kwargs_for(cred: AICredential) -> dict:
    spec = PROVIDERS[cred.provider]
    return await call_kwargs(
        spec, cred.model, decrypt_json(cred.encrypted_credentials), cred.config,
        get_settings().allow_private_llm_endpoints,
    )


async def resolve_llm(workspace_id: uuid.UUID) -> dict | None:
    """Workspace default provider first, then the operator's server-wide key, else None (heuristic)."""
    async with SessionLocal() as session:
        cred = await session.scalar(
            select(AICredential)
            .where(AICredential.workspace_id == workspace_id, AICredential.is_default.is_(True))
            .limit(1)
        )
    if cred is not None and cred.provider in PROVIDERS:
        return await kwargs_for(cred)
    return server_default_llm()
