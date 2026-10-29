import asyncio
import uuid

from temporalio import activity

from alphaview_common import clickhouse, contracts
from alphaview_common.signals import Signal
from alphaview_common.temporal import run_worker
from alphaview_nlp.pipeline import annotate, cluster_signals

ANNOTATIONS_DDL = """
CREATE TABLE IF NOT EXISTS signal_annotations (
    run_id UUID,
    id String,
    sentiment Float32,
    intent LowCardinality(String),
    annotated_at DateTime('UTC') DEFAULT now()
) ENGINE = ReplacingMergeTree
PARTITION BY toYYYYMM(annotated_at)
ORDER BY (run_id, id)
TTL annotated_at + INTERVAL 180 DAY
"""


async def store_annotations(run_id: uuid.UUID, signals: list[Signal]) -> None:
    if not signals:
        return
    rows = [[run_id, s.id, s.sentiment, s.intent] for s in signals]
    await (await clickhouse.get_client()).insert(
        "signal_annotations", rows, column_names=["run_id", "id", "sentiment", "intent"]
    )


@activity.defn(name=contracts.ANALYZE_SIGNALS)
async def analyze_signals(run_id: str, query: str) -> list[dict]:
    rid = uuid.UUID(run_id)
    signals = await clickhouse.fetch_signals(rid)
    # CPU-bound scikit-learn work must not block the worker's event loop.
    await asyncio.to_thread(annotate, signals)
    await store_annotations(rid, signals)
    return await asyncio.to_thread(cluster_signals, signals, query)


async def main() -> None:
    await (await clickhouse.get_client()).command(ANNOTATIONS_DDL)
    await run_worker(contracts.NLP_QUEUE, [analyze_signals], max_concurrent_activities=8)


if __name__ == "__main__":
    asyncio.run(main())
