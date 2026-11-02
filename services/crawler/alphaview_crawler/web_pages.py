import asyncio
import hashlib
import ipaddress
import json
import socket
from collections import defaultdict
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import aiohttp
from aiohttp.abc import AbstractResolver
from trafilatura import extract, load_html

from alphaview_common.signals import Signal

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_WEB_PAGES = 15
MAX_PAGES_PER_HOST = 2


class RequestPermitDenied(ValueError):
    pass


def checked_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Only public HTTPS pages on port 443 are allowed")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private or reserved address")
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))


class PublicResolver(AbstractResolver):
    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[dict]:
        addresses = await asyncio.get_running_loop().getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise OSError("Private or reserved destination blocked")
        return [{"hostname": host, "host": item[4][0], "port": port, "family": item[0],
                 "proto": 0, "flags": socket.AI_NUMERICHOST} for item in addresses]

    async def close(self) -> None:
        pass


def paywall_flag(value) -> bool:
    if isinstance(value, dict):
        if str(value.get("isAccessibleForFree", "")).lower() == "false":
            return True
        return any(paywall_flag(child) for child in value.values())
    return isinstance(value, list) and any(paywall_flag(child) for child in value)


def article_signal(body: bytes, url: str, since: datetime) -> Signal | None:
    tree = load_html(body)
    if tree is None:
        return None
    for script in tree.xpath('//script[@type="application/ld+json"]'):
        try:
            if paywall_flag(json.loads(script.text or "null")):
                return None
        except (ValueError, RecursionError):
            continue
    result = extract(tree, url=url, output_format="json", with_metadata=True, include_comments=False,
                     favor_precision=True, date_extraction_params={"extensive_search": False})
    if not result:
        return None
    article = json.loads(result)
    text = article.get("text") or ""
    if not article.get("date") or len(text) < 200:
        return None
    try:
        created = datetime.fromisoformat(article["date"].replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
    except ValueError:
        return None
    if created < since or created > datetime.now(UTC):
        return None
    return Signal(source="web", external_id=url, url=url, title=(article.get("title") or url)[:200],
                  text=text[:4000], created_at=created)


class PageFetcher:
    def __init__(self, session: aiohttp.ClientSession, user_agent: str, outcomes: list[dict] | None = None):
        self.session = session
        self.user_agent = user_agent
        self.rules: dict[str, RobotFileParser | None] = {}
        self.locks = defaultdict(asyncio.Lock)
        self.last_request: dict[str, float] = {}
        self.pages_per_host: dict[str, int] = defaultdict(int)
        self.outcomes = outcomes
        self.request_permit = None

    async def pause(self, origin: str, delay: float = 1) -> None:
        now = asyncio.get_running_loop().time()
        remaining = delay - (now - self.last_request.get(origin, 0))
        if remaining > 0:
            await asyncio.sleep(remaining)
        self.last_request[origin] = asyncio.get_running_loop().time()

    async def get(self, url: str) -> tuple[int, dict, bytes]:
        if self.request_permit is not None:
            await self.request_permit(url)
        async with self.session.get(checked_url(url), allow_redirects=False) as response:
            if response.content_length and response.content_length > MAX_PAGE_BYTES:
                raise ValueError("Page exceeds size limit")
            body = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                body.extend(chunk)
                if len(body) > MAX_PAGE_BYTES:
                    raise ValueError("Page exceeds size limit")
            return response.status, {name.lower(): value for name, value in response.headers.items()}, bytes(body)

    def extract_document(self, body: bytes, url: str, since: datetime):
        return article_signal(body, url, since)

    async def robots(self, origin: str) -> RobotFileParser | None:
        if origin in self.rules:
            return self.rules[origin]
        url = origin + "/robots.txt"
        rules = None
        for _ in range(4):
            await self.pause(origin)
            status, headers, body = await self.get(url)
            if status in (301, 302, 303, 307, 308):
                destination = checked_url(urljoin(url, headers.get("location", "")))
                if urlsplit(destination).netloc != urlsplit(origin).netloc:
                    break
                url = destination
                continue
            if status == 404 or status == 200:
                rules = RobotFileParser()
                rules.parse(body.decode("utf-8", errors="replace").splitlines() if status == 200 else [])
            break
        self.rules[origin] = rules
        return rules

    async def fetch(self, url: str, since: datetime) -> Signal | None:
        requested_url = url

        def finish(outcome, detail, signal=None):
            if self.outcomes is not None:
                self.outcomes.append({"source": "web", "requested_url": requested_url, "final_url": url,
                                      "outcome": outcome, "detail": detail, "signal_count": int(signal is not None)})
            return signal

        try:
            for _ in range(4):
                url = checked_url(url)
                parsed = urlsplit(url)
                origin = f"{parsed.scheme}://{parsed.netloc}"
                async with self.locks[origin]:
                    rules = await self.robots(origin)
                    delay = max(1, rules.crawl_delay(self.user_agent) or 1) if rules else 1
                    if rules is None or not rules.can_fetch(self.user_agent, url) or delay > 10:
                        return finish("blocked", "Robots permission unavailable, excluded, or throttle exceeds allowance")
                    if self.pages_per_host[parsed.hostname] >= MAX_PAGES_PER_HOST:
                        return finish("budget_limited", "Per-domain page limit reached")
                    self.pages_per_host[parsed.hostname] += 1
                    await self.pause(origin, delay)
                    status, headers, body = await self.get(url)
                if status in (301, 302, 303, 307, 308):
                    url = urljoin(url, headers.get("location", ""))
                    continue
                if status != 200:
                    outcome = "blocked" if status in (401, 403) else "rate_limited" if status == 429 else "failed"
                    return finish(outcome, f"HTTP {status}")
                if "text/html" not in headers.get("content-type", "").lower():
                    return finish("unsupported", "Response is not HTML")
                signal = await asyncio.to_thread(self.extract_document, body, url, since)
                return finish("fetched" if signal else "extraction_failed",
                              "Article extracted" if signal else "Quick extraction rejected paywall, missing date, old date or insufficient text", signal)
        except (aiohttp.ClientError, OSError, ValueError, TimeoutError, RecursionError) as exc:
            if isinstance(exc, RequestPermitDenied):
                return finish("budget_limited", "Request denied by budget, deadline or cancellation")
            return finish("failed", type(exc).__name__)
        return finish("blocked", "Redirect limit reached")


async def crawl_web_pages(urls: list[str], since: datetime, user_agent: str, outcomes: list[dict] | None = None) -> list[Signal]:
    connector = aiohttp.TCPConnector(resolver=PublicResolver(), use_dns_cache=False, limit=4)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=20),
                                    headers={"User-Agent": user_agent}, trust_env=False) as session:
        fetcher = PageFetcher(session, user_agent, outcomes)
        pages = await asyncio.gather(*(fetcher.fetch(url, since) for url in list(dict.fromkeys(urls))[:MAX_WEB_PAGES]))
    unique: dict[str, Signal] = {}
    for page in pages:
        if page:
            fingerprint = hashlib.sha256(" ".join(page.text.lower().split()).encode()).hexdigest()
            if fingerprint in unique and outcomes is not None:
                for outcome in outcomes:
                    if outcome.get("final_url") == page.url:
                        outcome.update(outcome="duplicate", detail="Duplicate extracted content", signal_count=0)
            unique.setdefault(fingerprint, page)
    return list(unique.values())