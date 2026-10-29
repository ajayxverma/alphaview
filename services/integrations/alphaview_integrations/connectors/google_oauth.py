from urllib.parse import urlencode

import httpx

from alphaview_integrations.config import get_settings
from alphaview_integrations.connectors.base import ConnectorError, raise_for

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def is_configured() -> bool:
    s = get_settings()
    return bool(s.google_client_id and s.google_client_secret)


def authorization_url(state: str, scopes: list[str]) -> str:
    s = get_settings()
    params = {
        "client_id": s.google_client_id,
        "redirect_uri": s.oauth_redirect_url,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(client: httpx.AsyncClient, code: str) -> dict:
    s = get_settings()
    resp = await client.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "redirect_uri": s.oauth_redirect_url,
            "grant_type": "authorization_code",
        },
    )
    raise_for(resp, "Google OAuth")
    tokens = resp.json()
    if "refresh_token" not in tokens:
        raise ConnectorError("Google did not return a refresh token; revoke access and retry")
    return {"refresh_token": tokens["refresh_token"]}


async def access_token(client: httpx.AsyncClient, creds: dict) -> str:
    s = get_settings()
    resp = await client.post(
        TOKEN_URL,
        data={
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    raise_for(resp, "Google OAuth")
    return resp.json()["access_token"]
