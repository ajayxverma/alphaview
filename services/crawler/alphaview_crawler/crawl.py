import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx

from alphaview_common.signals import Signal
from alphaview_crawler.adapters.base import INTENT_EXPANSIONS, SourceAdapter
from alphaview_crawler.adapters.hackernews import HackerNewsAdapter
from alphaview_crawler.adapters.reddit import RedditAdapter
from alphaview_crawler.adapters.stackexchange import StackExchangeAdapter
from alphaview_crawler.config import get_settings

log = logging.getLogger(__name__)

ADAPTERS: dict[str, SourceAdapter] = {a.id: a for a in (RedditAdapter(), HackerNewsAdapter(), StackExchangeAdapter())}


async def crawl(query: str, sources: list[str]) -> list[Signal]:
    """Run every (source x intent-expansion) search with bounded concurrency and dedupe by signal id."""
    s = get_settings()
    since = datetime.now(UTC) - timedelta(days=s.crawler_lookback_days)
    adapters = [ADAPTERS[x] for x in sources if x in ADAPTERS]
    sem = asyncio.Semaphore(4)

    async with httpx.AsyncClient(
        timeout=20, headers={"User-Agent": s.crawler_user_agent}, follow_redirects=True
    ) as client:

        async def one(adapter: SourceAdapter, q: str) -> list[Signal]:
            async with sem:
                try:
                    return await adapter.search(client, q, since)
                except httpx.HTTPError as exc:
                    log.warning("crawl failed source=%s q=%r err=%s", adapter.id, q, exc)
                    return []

        tasks = [one(a, f"{query} {exp}".strip()) for a in adapters for exp in INTENT_EXPANSIONS]
        batches = await asyncio.gather(*tasks)

    unique: dict[str, Signal] = {}
    for batch in batches:
        for sig in batch:
            if sig.content:
                unique.setdefault(sig.id, sig)
    return list(unique.values())
