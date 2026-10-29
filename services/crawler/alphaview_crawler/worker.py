import asyncio
import uuid

from temporalio import activity

from alphaview_common import clickhouse, contracts
from alphaview_common.signals import Signal
from alphaview_common.temporal import run_worker
from alphaview_crawler.crawl import crawl


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
async def crawl_sources(run_id: str, query: str, sources: list[str]) -> int:
    signals = await crawl(query, sources)
    await insert_signals(uuid.UUID(run_id), signals)
    return len(signals)


async def main() -> None:
    await (await clickhouse.get_client()).command(clickhouse.SIGNALS_DDL)
    await run_worker(contracts.CRAWLER_QUEUE, [crawl_sources])


if __name__ == "__main__":
    asyncio.run(main())
