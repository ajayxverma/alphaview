import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from temporalio import activity

from alphaview_common import clickhouse, contracts
from alphaview_discovery.config import get_settings
from alphaview_discovery.evidence import DocumentInput, ensure_state, store_attempts, store_document
from alphaview_discovery.evidence_models import ResearchState
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
        return {
            "query": run.query,
            "sources": run.sources,
            "workspace_id": str(run.workspace_id),
            "geo": run.geo,
            "research_config": run.research_config,
        }


@activity.defn(name=contracts.RECORD_RESEARCH_CRAWL)
async def record_research_crawl(run_id: str, result: dict) -> list[str]:
    signals = await clickhouse.fetch_signals(uuid.UUID(run_id)) if result.get("count") else []
    documents = []
    async with SessionLocal() as session:
        run = await _get_run(session, run_id)
        await store_attempts(session, run.id, run.workspace_id, result.get("attempts") or [])
        for index, signal in enumerate(signals):
            if index % 20 == 0:
                activity.heartbeat({"documents_recorded": index})
            published_at = signal.created_at if signal.created_at.tzinfo else signal.created_at.replace(tzinfo=UTC)
            document = DocumentInput(
                requested_url=signal.url, final_url=signal.url, title=signal.title[:500], source=signal.source,
                text=signal.content[:64000], published_at=published_at,
                document_type="article" if signal.source in ("web", "devto") else "discussion",
                extraction_method="quick_signal_snapshot", truncated=True,
                provenance={"signal_id": signal.id, "run_query": run.query, "geography": "approximate" if run.geo else "global"},
            )
            documents.append(str(await store_document(session, run.id, run.workspace_id, document)))
        await session.commit()
    return documents


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
        await ensure_state(session, run)
        state = await session.scalar(select(ResearchState).where(ResearchState.run_id == run.id))
        state.phase = status
        state.updated_at = datetime.now(UTC)
        if status in (RunStatus.completed.value, RunStatus.failed.value):
            state.stop_reason = "quick_pass_complete" if status == RunStatus.completed.value else "source_or_workflow_failure"
            state.complete = False
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


LOCAL_ACTIVITIES = [get_run, set_status, rank_clusters, persist_opportunities, record_research_crawl]
