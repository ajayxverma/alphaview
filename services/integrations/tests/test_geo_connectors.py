import json

import httpx

from alphaview_integrations.connectors.ga4 import _geo_filters
from alphaview_integrations.connectors.gsc import alpha3
from alphaview_integrations.connectors.registry import REGISTRY
from alphaview_integrations.connectors.semrush import semrush_database

LONDON = {"label": "London, England, United Kingdom", "lat": 51.5072, "lon": -0.1276, "radius_km": 25,
          "country_code": "GB", "country": "United Kingdom", "region": "England", "city": "London"}


def capture(payload) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), seen


async def test_dataforseo_uses_coordinate_radius():
    client, seen = capture({"tasks": [{"result": []}]})
    async with client:
        await REGISTRY["dataforseo"].enrich(client, {"login": "l", "password": "p"}, {}, ["kw"], LONDON)
    task = json.loads(seen[0].content)[0]
    assert task["location_coordinate"] == "51.507200,-0.127600,25"
    assert "location_code" not in task


async def test_dataforseo_without_geo_uses_location_code():
    client, seen = capture({"tasks": [{"result": []}]})
    async with client:
        await REGISTRY["dataforseo"].enrich(client, {"login": "l", "password": "p"}, {}, ["kw"])
    assert json.loads(seen[0].content)[0]["location_code"] == 2840


async def test_serpapi_localises_trends_and_serp():
    client, seen = capture({})
    async with client:
        await REGISTRY["serpapi"].enrich(client, {"api_key": "k"}, {}, ["kw"], LONDON)
    params = [dict(r.url.params) for r in seen]
    trends = next(p for p in params if p["engine"] == "google_trends")
    serp = next(p for p in params if p["engine"] == "google")
    assert trends["geo"] == "GB"
    assert serp["gl"] == "gb" and serp["location"] == LONDON["label"]


def test_country_mappings():
    assert semrush_database(LONDON) == "uk"
    assert semrush_database({"country_code": "ZZ"}) is None
    assert alpha3("GB") == "gbr"
    fields = [e["filter"]["fieldName"] for e in _geo_filters(LONDON)]
    assert fields == ["countryId", "city"]
    assert [e["filter"]["fieldName"] for e in _geo_filters({**LONDON, "radius_km": 600})] == ["countryId"]
