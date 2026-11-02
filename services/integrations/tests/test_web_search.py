import json

import httpx
import pytest

from alphaview_integrations.web_search import normalize_url, search_queries, search_urls


def test_search_urls_reject_credentials_ports_and_deduplicate_fragments():
    assert normalize_url("https://Example.com/blog#one") == "https://example.com/blog"
    assert normalize_url("https://key:secret@example.com") is None
    assert normalize_url("https://example.com:8443/blog") is None
    assert normalize_url("http://example.com/blog") is None
    assert "Austin" in search_queries("invoices", {"city": "Austin", "radius_km": 25})[0]


@pytest.mark.parametrize("provider", ["serpapi", "dataforseo"])
async def test_search_parses_only_organic_urls_and_preserves_location(provider):
    requests = []

    def respond(request):
        requests.append(request)
        if provider == "serpapi":
            return httpx.Response(200, json={"organic_results": [{"link": "https://example.com/blog#fragment"}],
                                            "ads": [{"link": "https://ads.example.com"}]})
        return httpx.Response(200, json={"status_code": 20000, "tasks": [{"status_code": 20000,
            "result": [{"items": [{"type": "organic", "url": "https://example.com/blog#fragment"},
                                   {"type": "paid", "url": "https://ads.example.com"}]}]}]})

    geo = {"lat": 30.27, "lon": -97.74, "city": "Austin", "label": "Austin, Texas", "country_code": "US"}
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        urls = await search_urls(client, provider, {"api_key": "test", "login": "user", "password": "test"}, {}, "invoices", geo)
    assert urls == ["https://example.com/blog"]
    assert len(requests) == 3
    if provider == "serpapi":
        assert requests[0].url.params["location"] == "Austin, Texas"
    else:
        assert json.loads(requests[0].content)[0]["location_coordinate"] == "30.27,-97.74"


async def test_dataforseo_task_errors_are_not_treated_as_empty_success():
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status_code": 20000, "tasks": [{"status_code": 40200}]})
    )) as client:
        with pytest.raises(ValueError, match="rejected"):
            await search_urls(client, "dataforseo", {"login": "user", "password": "test"}, {}, "invoices", None)