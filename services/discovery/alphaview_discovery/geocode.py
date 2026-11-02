"""Place search / reverse geocoding via a Nominatim-compatible API, cached in Redis."""

import hashlib
import json

import httpx

from alphaview_common.ratelimit import redis
from alphaview_discovery.config import get_settings

CACHE_TTL_SECONDS = 7 * 24 * 3600


def _place(item: dict) -> dict:
    addr = item.get("address") or {}
    return {
        "label": item.get("display_name", "")[:300],
        "lat": float(item["lat"]),
        "lon": float(item["lon"]),
        "country_code": (addr.get("country_code") or "").upper() or None,
        "country": addr.get("country"),
        "region": addr.get("state") or addr.get("region") or addr.get("county"),
        "city": addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality"),
    }


async def _cached_get(path: str, params: dict) -> object:
    s = get_settings()
    key = "geo:" + hashlib.sha1(f"{path}?{sorted(params.items())}".encode()).hexdigest()
    if cached := await redis.get(key):
        return json.loads(cached)
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": s.geocoder_user_agent}) as client:
        resp = await client.get(f"{s.geocoder_url}{path}", params={**params, "format": "jsonv2", "addressdetails": 1})
        resp.raise_for_status()
        data = resp.json()
    await redis.set(key, json.dumps(data), ex=CACHE_TTL_SECONDS)
    return data


async def search_places(q: str, limit: int = 6) -> list[dict]:
    data = await _cached_get("/search", {"q": q, "limit": limit})
    return [_place(i) for i in data if isinstance(i, dict) and "lat" in i] if isinstance(data, list) else []


async def reverse_place(lat: float, lon: float) -> dict | None:
    data = await _cached_get("/reverse", {"lat": round(lat, 4), "lon": round(lon, 4), "zoom": 10})
    return _place(data) if isinstance(data, dict) and "lat" in data else None
