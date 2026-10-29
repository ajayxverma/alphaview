import pytest
from cryptography.fernet import Fernet

from alphaview_common import security
from alphaview_common.settings import get_common_settings as get_settings


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(get_settings(), "encryption_key", Fernet.generate_key().decode())


def test_password_roundtrip():
    h = security.hash_password("correct horse battery")
    assert security.verify_password("correct horse battery", h)
    assert not security.verify_password("wrong", h)


def test_token_purpose_enforced():
    import uuid

    import jwt

    uid = uuid.uuid4()
    oauth = security.create_token(uid, purpose="oauth")
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_token(oauth, purpose="access")
    assert security.decode_token(oauth, purpose="oauth")["sub"] == str(uid)


def test_credentials_encryption():
    blob = security.encrypt_json({"api_key": "secret"})
    assert "secret" not in blob
    assert security.decrypt_json(blob) == {"api_key": "secret"}
