import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from temporalio import activity

from alphaview_common import clickhouse, contracts
from alphaview_common.signals import Signal
from alphaview_common.temporal import run_worker
from alphaview_crawler.config import get_settings
from alphaview_crawler.crawl import crawl
from alphaview_crawler.deep_read import deep_read
from alphaview_crawler.web_pages import crawl_web_pages


async def insert_signals(run_id: uuid.UUID, signals: list[Signal]) -> None:
    if not signals:
        return
    rows = [
        [
            run_id, s.id, s.source, s.external_id, s.url, s.title, s.text, s.created_at,
            s.engagement, s.comments, None if s.answered is None else int(s.answered),
        ]
        for s in signals
    ]
    await (await clickhouse.get_client()).insert("signals", rows, column_names=clickhouse.SIGNAL_COLUMNS)


@activity.defn(name=contracts.CRAWL_SOURCES)
async def crawl_sources(
    run_id: str, query: str, sources: list[str], geo: dict | None = None, web_urls: list[str] | None = None,
    collect_outcomes: bool = False,
) -> int | dict:
    outcomes = [] if collect_outcomes else None
    signals = await crawl(query, sources, geo, outcomes)
    if "web" in sources and web_urls:
        settings = get_settings()
        since = datetime.now(UTC) - timedelta(days=settings.crawler_lookback_days)
        signals += await crawl_web_pages(web_urls, since, settings.crawler_user_agent, outcomes)
    await insert_signals(uuid.UUID(run_id), signals)
    return {"count": len(signals), "attempts": outcomes} if collect_outcomes else len(signals)


async def main() -> None:
    await (await clickhouse.get_client()).command(clickhouse.SIGNALS_DDL)
    await run_worker(contracts.CRAWLER_QUEUE, [crawl_sources, deep_read_activity])


@activity.defn(name=contracts.DEEP_READ)
async def deep_read_activity(operation_id: str, run_id: str, workspace_id: str, url: str, options: dict) -> dict:
    return await deep_read(operation_id, run_id, workspace_id, url, options, get_settings().research_ingest_url)


if __name__ == "__main__":
    asyncio.run(main())
