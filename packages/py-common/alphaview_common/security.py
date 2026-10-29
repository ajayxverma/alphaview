import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.fernet import Fernet

from alphaview_common.settings import get_common_settings as get_settings

_hasher = PasswordHasher()
_ALGO = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


def create_token(subject: uuid.UUID, purpose: str = "access", ttl: timedelta | None = None, **claims: Any) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "purpose": purpose,
        "iat": now,
        "exp": now + (ttl or timedelta(minutes=s.jwt_ttl_minutes)),
        **claims,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=_ALGO)


def decode_token(token: str, purpose: str = "access") -> dict[str, Any]:
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGO])
    if payload.get("purpose") != purpose:
        raise jwt.InvalidTokenError("wrong token purpose")
    return payload


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return Fernet(key.encode())


def encrypt_json(data: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_json(token: str) -> dict[str, Any]:
    return json.loads(_fernet().decrypt(token.encode()))
