import asyncio
import json
import socket
from datetime import UTC, datetime

import pytest

from alphaview_crawler.web_pages import MAX_PAGE_BYTES, PageFetcher, PublicResolver, article_signal, checked_url


def article(paywall=False):
    text = ("I am frustrated with invoice software and wish there was a reliable alternative. " * 12)
    return f'''<html><head><title>Invoice pain points</title>
    <meta property="article:published_time" content="2026-10-30T12:00:00Z">
    <script type="application/ld+json">{json.dumps({"isAccessibleForFree": not paywall})}</script>
    </head><body><article><h1>Invoice pain points</h1><p>{text}</p></article></body></html>'''.encode()


def test_extracts_dated_article_and_rejects_paywall_and_old_date():
    signal = article_signal(article(), "https://example.com/post", datetime(2026, 10, 1, tzinfo=UTC))
    assert signal and signal.source == "web" and "frustrated" in signal.text
    assert signal.url == "https://example.com/post"
    assert article_signal(article(True), signal.url, datetime(2026, 10, 1, tzinfo=UTC)) is None
    assert article_signal(article(), signal.url, datetime(2026, 11, 1, tzinfo=UTC)) is None


@pytest.mark.parametrize("url", ["https://127.0.0.1/", "https://169.254.169.254/", "https://[::1]/",
                                  "https://user:pass@example.com/", "http://example.com/", "https://example.com:8443/"])
def test_blocks_unsafe_page_urls(url):
    with pytest.raises(ValueError):
        checked_url(url)


async def test_robots_disallow_prevents_page_request(monkeypatch):
    fetcher = PageFetcher(None, "alphaview-bot")
    seen = []

    async def get(url):
        seen.append(url)
        return 200, {}, b"User-agent: *\nDisallow: /"

    monkeypatch.setattr(fetcher, "get", get)
    assert await fetcher.fetch("https://example.com/post", datetime(2026, 10, 1, tzinfo=UTC)) is None
    assert seen == ["https://example.com/robots.txt"]


async def test_private_redirect_is_blocked(monkeypatch):
    fetcher = PageFetcher(None, "alphaview-bot")
    seen = []

    async def get(url):
        seen.append(url)
        if url.endswith("robots.txt"):
            return 404, {}, b""
        return 302, {"location": "https://169.254.169.254/latest"}, b""

    async def pause(*args):
        pass

    monkeypatch.setattr(fetcher, "get", get)
    monkeypatch.setattr(fetcher, "pause", pause)
    assert await fetcher.fetch("https://example.com/post", datetime(2026, 10, 1, tzinfo=UTC)) is None
    assert len(seen) == 2


async def test_dns_resolution_blocks_private_destinations(monkeypatch):
    async def resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    with pytest.raises(OSError, match="blocked"):
        await PublicResolver().resolve("rebound.example.com", 443)


async def test_oversized_response_is_rejected_before_reading():
    class Response:
        content_length = MAX_PAGE_BYTES + 1

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    with pytest.raises(ValueError, match="size limit"):
        await PageFetcher(Session(), "alphaview-bot").get("https://example.com/large")


async def test_redirect_destination_gets_its_own_robots_check(monkeypatch):
    fetcher = PageFetcher(None, "alphaview-bot")
    seen = []

    async def get(url):
        seen.append(url)
        if url == "https://other.example.com/robots.txt":
            return 200, {}, b"User-agent: *\nDisallow: /"
        if url.endswith("robots.txt"):
            return 404, {}, b""
        return 302, {"location": "https://other.example.com/post"}, b""

    async def pause(*args):
        pass

    monkeypatch.setattr(fetcher, "get", get)
    monkeypatch.setattr(fetcher, "pause", pause)
    assert await fetcher.fetch("https://example.com/post", datetime(2026, 10, 1, tzinfo=UTC)) is None
    assert seen[-1] == "https://other.example.com/robots.txt"