import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx

from alphaview_common.geo import CITY_MAX_KM, Geo, place_name
from alphaview_common.signals import Signal
from alphaview_crawler.adapters.base import INTENT_EXPANSIONS, SourceAdapter
from alphaview_crawler.adapters.devto import DevCommunityAdapter
from alphaview_crawler.adapters.github import GitHubAdapter
from alphaview_crawler.adapters.hackernews import HackerNewsAdapter
from alphaview_crawler.adapters.mastodon import MastodonAdapter
from alphaview_crawler.adapters.reddit import RedditAdapter
from alphaview_crawler.adapters.stackexchange import StackExchangeAdapter
from alphaview_crawler.config import get_settings

log = logging.getLogger(__name__)

ADAPTERS: dict[str, SourceAdapter] = {
    adapter.id: adapter for adapter in (
        RedditAdapter(), HackerNewsAdapter(), StackExchangeAdapter(),
        MastodonAdapter(), GitHubAdapter(), DevCommunityAdapter(),
    )
}


def build_queries(query: str, geo: Geo | None) -> list[str]:
    """Intent-expanded queries; when a location is set the place name scopes every query."""
    place = place_name(geo)
    base = f"{query} {place}" if place else query
    return [f"{base} {exp}".strip() for exp in INTENT_EXPANSIONS]


def local_subreddit(geo: Geo | None) -> str | None:
    if not geo or geo.get("radius_km", CITY_MAX_KM) > CITY_MAX_KM or not geo.get("city"):
        return None
    name = re.sub(r"[^a-z0-9]", "", geo["city"].lower())
    return name if 3 <= len(name) <= 21 else None


async def crawl(query: str, sources: list[str], geo: Geo | None = None, outcomes: list[dict] | None = None) -> list[Signal]:
    """Run every (source x intent-expansion) search with bounded concurrency and dedupe by signal id."""
    s = get_settings()
    since = datetime.now(UTC) - timedelta(days=s.crawler_lookback_days)
    adapters = [ADAPTERS[x] for x in sources if x in ADAPTERS]
    sem = asyncio.Semaphore(4)

    async with httpx.AsyncClient(
        timeout=20, headers={"User-Agent": s.crawler_user_agent}, follow_redirects=True
    ) as client:

        async def one(adapter: SourceAdapter, q: str, **kwargs) -> list[Signal]:
            async with sem:
                try:
                    signals = await adapter.search(client, q, since, **kwargs)
                    if outcomes is not None:
                        outcomes.append({"source": adapter.id, "query": q, "outcome": "fetched" if signals else "no_results",
                                         "signal_count": len(signals), "detail": "Source search completed"})
                    return signals
                except httpx.HTTPError as exc:
                    status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                    outcome = "blocked" if status in (401, 403) else "rate_limited" if status == 429 else "failed"
                    if outcomes is not None:
                        outcomes.append({"source": adapter.id, "query": q, "outcome": outcome, "signal_count": 0,
                                         "detail": f"HTTP {status}" if status else type(exc).__name__})
                    log.warning("crawl failed source=%s q=%r err=%s", adapter.id, q, exc)
                    return []
                except (ValueError, KeyError, TypeError):
                    if outcomes is not None:
                        outcomes.append({"source": adapter.id, "query": q, "outcome": "extraction_failed",
                                         "signal_count": 0, "detail": "Source returned an unsupported payload"})
                    return []

        queries = build_queries(query, geo)
        tasks = [
            one(adapter, scoped_query) for adapter in adapters
            for scoped_query in (queries[:1] if adapter.id in {"devto", "mastodon"} else queries)
        ]
        subreddit = local_subreddit(geo)
        if subreddit and "reddit" in sources:
            # The city's own community, searched without the place name it already implies.
            tasks += [one(ADAPTERS["reddit"], f"{query} {exp}".strip(), subreddit=subreddit) for exp in INTENT_EXPANSIONS]
        batches = await asyncio.gather(*tasks)

    unique: dict[str, Signal] = {}
    for batch in batches:
        for sig in batch:
            if sig.content:
                unique.setdefault(sig.id, sig)
    return list(unique.values())
