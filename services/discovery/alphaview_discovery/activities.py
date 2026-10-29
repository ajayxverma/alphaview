import uuid
from datetime import UTC, datetime

from sqlalchemy import delete
from temporalio import activity

from alphaview_common import contracts
from alphaview_discovery.config import get_settings
from alphaview_discovery.gap import score_gap
from alphaview_discovery.models import DiscoveryRun, Opportunity, RunStatus, SessionLocal


async def _get_run(session, run_id: str) -> DiscoveryRun:
    run = await session.get(DiscoveryRun, uuid.UUID(run_id))
    if run is None:
        raise ValueError(f"run {run_id} not found")
    return run


@activity.defn(name=contracts.GET_RUN)
async def get_run(run_id: str) -> dict:
    async with SessionLocal() as session:
        run = await _get_run(session, run_id)
        return {"query": run.query, "sources": run.sources, "workspace_id": str(run.workspace_id)}


@activity.defn(name=contracts.SET_STATUS)
async def set_status(run_id: str, status: str, error: str | None = None, signal_count: int | None = None) -> None:
    async with SessionLocal() as session:
        run = await _get_run(session, run_id)
        run.status = status
        run.error = error
        if signal_count is not None:
            run.signal_count = signal_count
        if status in (RunStatus.completed.value, RunStatus.failed.value):
            run.finished_at = datetime.now(UTC)
        await session.commit()


@activity.defn(name=contracts.RANK_CLUSTERS)
async def rank_clusters(clusters: list[dict], enrichment: dict) -> list[dict]:
    scored = [
        {"cluster": c, "scored": score_gap(c, enrichment["kw_metrics"], enrichment["connectors_used"])}
        for c in clusters
    ]
    scored.sort(key=lambda r: r["scored"]["gap_score"], reverse=True)
    return scored[: get_settings().max_opportunities]


@activity.defn(name=contracts.PERSIST_OPPORTUNITIES)
async def persist_opportunities(run_id: str, ranked: list[dict], strategies: list[dict]) -> int:
    async with SessionLocal() as session:
        run = await _get_run(session, run_id)
        # Idempotent on activity retry.
        await session.execute(delete(Opportunity).where(Opportunity.run_id == run.id))
        for item, strategy in zip(ranked, strategies, strict=True):
            cluster, sc = item["cluster"], item["scored"]
            session.add(
                Opportunity(
                    run_id=run.id,
                    workspace_id=run.workspace_id,
                    title=strategy["title"][:200],
                    cluster_label=cluster["label"][:200],
                    keywords=cluster["keywords"],
                    gap_score=sc["gap_score"],
                    confidence=sc["confidence"],
                    metrics=sc["metrics"],
                    evidence=cluster["evidence"],
                    strategy=strategy,
                )
            )
        await session.commit()
    return len(ranked)


LOCAL_ACTIVITIES = [get_run, set_status, rank_clusters, persist_opportunities]
