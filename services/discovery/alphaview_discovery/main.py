import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from temporalio.client import Client
from temporalio.service import RPCError

from alphaview_common import contracts, ratelimit, temporal
from alphaview_common.auth import Principal, get_principal
from alphaview_common.web import create_app
from alphaview_discovery.config import get_settings
from alphaview_discovery.deep_api import initialize_deep
from alphaview_discovery.deep_api import router as deep_router
from alphaview_discovery.evidence import require_run, search_passages
from alphaview_discovery.evidence_models import (
    ResearchAttempt,
    ResearchCandidate,
    ResearchDocument,
    ResearchState,
    ResearchVersion,
)
from alphaview_discovery.geocode import reverse_place, search_places
from alphaview_discovery.models import DiscoveryRun, Opportunity, RunStatus, get_db, init_db
from alphaview_discovery.schemas import DiscoveryCreate, OpportunityOut, RunDetailOut, RunOut


@asynccontextmanager
async def lifespan(app):
    await init_db()
    app.state.temporal = await temporal.connect()
    yield


app = create_app("discovery", lifespan)
app.include_router(deep_router)


@app.get("/sources", tags=["discovery"])
async def list_sources() -> list[dict[str, str]]:
    return [{"id": k, "name": v} for k, v in contracts.SOURCES.items()]


@app.get("/geo/search", tags=["geo"])
async def geo_search(
    q: str = Query(min_length=2, max_length=200), principal: Principal = Depends(get_principal)
) -> list[dict]:
    await ratelimit.enforce(f"geo:{principal.workspace_id}", limit=120, window_seconds=600)
    try:
        return await search_places(q.strip())
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Location service unavailable") from exc


@app.get("/geo/reverse", tags=["geo"])
async def geo_reverse(
    lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180),
    principal: Principal = Depends(get_principal),
) -> dict:
    await ratelimit.enforce(f"geo:{principal.workspace_id}", limit=120, window_seconds=600)
    try:
        place = await reverse_place(lat, lon)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Location service unavailable") from exc
    if place is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No place found at these coordinates")
    return place


@app.post("/discovery", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED, tags=["discovery"])
async def start_discovery(
    body: DiscoveryCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryRun:
    s = get_settings()
    sources = [x for x in dict.fromkeys(body.sources) if x in contracts.SOURCES]
    if not sources and not (body.research.mode == "deep" and body.research.seed_urls):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Choose sources from: {', '.join(contracts.SOURCES)}"
        )
    if body.research.mode == "deep" and "web" not in sources and not body.research.seed_urls:
        raise HTTPException(422, "Deep mode needs Web & Blogs or explicit seed URLs; Quick community adapters remain available in Quick mode")
    await ratelimit.enforce(f"runs:{principal.workspace_id}", limit=s.max_runs_per_hour, window_seconds=3600)

    run = DiscoveryRun(
        workspace_id=principal.workspace_id,
        created_by=principal.user_id,
        query=body.query.strip(),
        sources=sources,
        geo=dict(body.location.to_geo()) if body.location else None,
    )
    db.add(run)
    await db.flush()
    if body.research.mode == "deep":
        await initialize_deep(db, run, body.research)
    else:
        run.research_config = body.research.model_dump(mode="json")
    await db.commit()

    client: Client = request.app.state.temporal
    try:
        workflow_name = contracts.DEEP_WORKFLOW if body.research.mode == "deep" else contracts.DISCOVERY_WORKFLOW
        workflow_id = f"deep-{run.id}-1" if body.research.mode == "deep" else f"discovery-{run.id}"
        await client.start_workflow(workflow_name, args=[str(run.id), 1] if body.research.mode == "deep" else [str(run.id)],
                        id=workflow_id, task_queue=contracts.DISCOVERY_QUEUE)
    except Exception as exc:
        run.status, run.error = RunStatus.failed.value, "Could not schedule workflow"
        await db.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Workflow engine unavailable") from exc
    return run


@app.get("/discovery", response_model=list[RunOut], tags=["discovery"])
async def list_runs(principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(DiscoveryRun)
        .where(DiscoveryRun.workspace_id == principal.workspace_id)
        .order_by(DiscoveryRun.created_at.desc())
        .limit(50)
    )
    return list(rows)


@app.get("/discovery/{run_id}", response_model=RunDetailOut, tags=["discovery"])
async def get_run(run_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    run = await db.scalar(
        select(DiscoveryRun).options(selectinload(DiscoveryRun.opportunities)).where(DiscoveryRun.id == run_id)
    )
    if run is None or run.workspace_id != principal.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run


@app.delete("/discovery/{run_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["discovery"])
async def delete_run(
    run_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    run = await db.get(DiscoveryRun, run_id)
    if run is None or run.workspace_id != principal.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    if run.status not in (RunStatus.completed.value, RunStatus.failed.value, RunStatus.cancelled.value):
        # Stop the pipeline first so its activities don't write to a deleted run.
        client: Client = request.app.state.temporal
        try:
            if (run.research_config or {}).get("mode") == "deep":
                state = await db.get(ResearchState, run.id)
                workflow_id = f"deep-{run.id}-{state.epoch}"
            else:
                workflow_id = f"discovery-{run.id}"
            await client.get_workflow_handle(workflow_id).terminate("Run deleted by user")
        except RPCError:
            pass  # already finished or never started
    await db.delete(run)  # opportunities cascade
    await db.commit()


@app.get("/opportunities", response_model=list[OpportunityOut], tags=["discovery"])
async def list_opportunities(
    min_score: float = 0, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
):
    rows = await db.scalars(
        select(Opportunity)
        .where(Opportunity.workspace_id == principal.workspace_id, Opportunity.gap_score >= min_score)
        .order_by(Opportunity.gap_score.desc())
        .limit(50)
    )
    return list(rows)


@app.get("/discovery/{run_id}/research", tags=["research"])
async def research_details(run_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    try:
        run = await require_run(db, run_id, principal.workspace_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found") from exc
    state = await db.scalar(select(ResearchState).where(ResearchState.run_id == run_id, ResearchState.workspace_id == principal.workspace_id))
    attempts = list(await db.scalars(select(ResearchAttempt).where(
        ResearchAttempt.run_id == run_id, ResearchAttempt.workspace_id == principal.workspace_id
    ).order_by(ResearchAttempt.retrieved_at.desc()).limit(100)))
    document_count = await db.scalar(select(func.count()).select_from(ResearchDocument).where(
        ResearchDocument.run_id == run_id, ResearchDocument.workspace_id == principal.workspace_id))
    deep_mode = (run.research_config or {}).get("mode") == "deep"
    versions = list(await db.scalars(select(ResearchVersion).where(ResearchVersion.run_id == run_id,
        ResearchVersion.workspace_id == principal.workspace_id).order_by(ResearchVersion.version.desc()).limit(10)))
    candidates = await db.scalar(select(func.count()).select_from(ResearchCandidate).where(
        ResearchCandidate.run_id == run_id, ResearchCandidate.workspace_id == principal.workspace_id))
    return {
        "available": state is not None, "mode": "deep" if deep_mode else "quick", "phase": state.phase if state else "legacy",
        "planner": state.planner if state else "legacy", "retrieval": "lexical_only",
        "budget": state.budget if state else None, "usage": state.usage if state else {},
        "coverage": state.coverage if state else {}, "unresolved": state.unresolved if state else [],
        "stop_reason": state.stop_reason if state else None, "complete": state.complete if state else False, "documents": document_count,
        "round": state.round if state else 0, "deadline": state.deadline if state else None, "candidates": candidates,
        "reports": [{"version": version.version, "created_at": version.created_at, "report": version.report} for version in versions],
        "limitations": ["Deep budgets are enforced with persistent operation reservations; ambiguous operations retain their reservation.",
                 "Lexical-only retrieval and context-checked source attributions, not statistical truth verification.",
                 "Reference pages are not customer demand; publication dates and language may be uncertain."] if deep_mode else ["Quick gap scoring and source sampling are unchanged.",
                         "Stored Quick snapshots may be truncated; complete reference extraction is not enabled.",
                         "Lexical-only retrieval; no embeddings, semantic reranker or verified Deep report.",
                         "Research budget enforcement is not enabled in legacy Quick mode."],
        "attempts": [{"source": item.source, "query": item.query, "requested_url": item.requested_url,
                      "final_url": item.final_url, "outcome": item.outcome, "detail": item.detail,
                      "signal_count": item.signal_count, "retrieved_at": item.retrieved_at} for item in attempts],
    }


@app.get("/discovery/{run_id}/evidence", tags=["research"])
async def evidence_search(
    run_id: uuid.UUID, q: str = Query(min_length=1, max_length=300), source: str | None = Query(default=None, max_length=60),
    document_type: str | None = Query(default=None, max_length=40), language: str | None = Query(default=None, pattern=r"^[a-z]{2}$"),
    date_from: datetime | None = None, date_to: datetime | None = None,
    principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "date_from must not be after date_to")
    try:
        results = await search_passages(db, run_id, principal.workspace_id, q, source, document_type, date_from, date_to, language)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found") from exc
    return {"retrieval": "lexical_only", "ranking": "PostgreSQL ts_rank_cd with simple tokenization (not BM25)", "results": results}


@app.get("/opportunities/{opportunity_id}", response_model=OpportunityOut, tags=["discovery"])
async def get_opportunity(
    opportunity_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
):
    opp = await db.get(Opportunity, opportunity_id)
    if opp is None or opp.workspace_id != principal.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    return opp
