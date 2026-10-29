import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from alphaview_common.security import decode_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    workspace_id: uuid.UUID


def principal_from_token(token: str) -> Principal:
    payload = decode_token(token)
    return Principal(user_id=uuid.UUID(payload["sub"]), workspace_id=uuid.UUID(payload["ws"]))


async def get_principal(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
    """Stateless auth: identity, workspace and expiry all come from the signed token."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        return principal_from_token(creds.credentials)
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated") from None
