import uuid

import jwt
import pytest

from alphaview_common.auth import principal_from_token
from alphaview_common.security import create_token


def test_principal_from_token_reads_workspace_claim():
    uid, ws = uuid.uuid4(), uuid.uuid4()
    p = principal_from_token(create_token(uid, ws=str(ws)))
    assert p.user_id == uid
    assert p.workspace_id == ws


def test_token_without_workspace_rejected():
    with pytest.raises(KeyError):
        principal_from_token(create_token(uuid.uuid4()))


def test_oauth_state_token_not_accepted_as_access():
    with pytest.raises(jwt.InvalidTokenError):
        principal_from_token(create_token(uuid.uuid4(), purpose="oauth", ws=str(uuid.uuid4())))
