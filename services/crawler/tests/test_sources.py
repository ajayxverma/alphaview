from datetime import UTC, datetime

import httpx
import pytest

from alphaview_common.contracts import SOURCES
from alphaview_crawler.crawl import ADAPTERS, build_queries, crawl, local_subreddit

GEO = {"label": "San Francisco, California, United States", "lat": 37.77, "lon": -122.42,
       "country_code": "US", "country": "United States", "region": "California", "city": "San Francisco"}


def test_adapters_match_published_sources():
    assert set(ADAPTERS) == set(SOURCES) - {"web"}


def test_queries_without_location_unchanged():
    assert build_queries("pet insurance", None)[0] == "pet insurance"


def test_queries_scoped_by_radius():
    assert build_queries("pet insurance", {**GEO, "radius_km": 25})[0] == "pet insurance San Francisco"
    assert build_queries("pet insurance", {**GEO, "radius_km": 400})[1] == "pet insurance California is there a tool"


def test_local_subreddit_only_for_city_radius():
    assert local_subreddit({**GEO, "radius_km": 25}) == "sanfrancisco"
    assert local_subreddit({**GEO, "radius_km": 800}) is None
    assert local_subreddit(None) is None


@pytest.mark.parametrize("source,payload,expected_url", [
    ("mastodon", [{"id": "123", "uri": "https://mastodon.social/users/sample/statuses/123",
        "url": "https://mastodon.social/@sample/123", "visibility": "public",
        "content": "<p>I wish invoice &amp; payment tools were easier</p>",
        "created_at": "2026-10-30T12:00:00Z", "favourites_count": 3, "replies_count": 2}],
        "https://mastodon.social/@sample/123"),
    ("github", {"items": [{"id": 12, "html_url": "https://github.com/org/repo/issues/12",
        "title": "Invoice sync broken", "body": None, "created_at": "2026-10-30T12:00:00Z",
        "comments": 2, "reactions": {"total_count": 3}}]}, "https://github.com/org/repo/issues/12"),
    ("devto", [{"id": 5, "url": "https://dev.to/person/invoices", "title": "Invoice automation",
        "description": "I wish this were easier", "published_at": "2026-10-30T12:00:00Z",
        "public_reactions_count": 3, "comments_count": 2}], "https://dev.to/person/invoices"),
])
async def test_public_adapters_normalize_and_filter_dates(source, payload, expected_url):
    def respond(request):
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        signals = await ADAPTERS[source].search(client, "invoice", datetime(2026, 10, 1, tzinfo=UTC))
        assert len(signals) == 1
        signal = signals[0]
        assert signal.source == source and signal.url == expected_url
        assert signal.engagement == 3 and signal.comments == 2
        assert signal.id and signal.content
        assert await ADAPTERS[source].search(client, "invoice", datetime(2026, 11, 1, tzinfo=UTC)) == []


async def test_source_failures_are_recorded_not_reported_as_empty_demand(monkeypatch):
    async def blocked(*args, **kwargs):
        request = httpx.Request("GET", "https://api.github.com/search/issues")
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("blocked", request=request, response=response)

    monkeypatch.setattr(ADAPTERS["github"], "search", blocked)
    outcomes = []
    assert await crawl("invoice", ["github"], outcomes=outcomes) == []
    assert len(outcomes) == 5
    assert all(outcome["outcome"] == "blocked" and outcome["detail"] == "HTTP 403" for outcome in outcomes)


async def test_successful_empty_search_is_distinguished_from_provider_failure(monkeypatch):
    async def empty(*args, **kwargs):
        return []

    monkeypatch.setattr(ADAPTERS["github"], "search", empty)
    outcomes = []
    await crawl("invoice", ["github"], outcomes=outcomes)
    assert all(outcome["outcome"] == "no_results" for outcome in outcomes)
