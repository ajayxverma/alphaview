import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from temporalio.client import Client

from alphaview_common import contracts, ratelimit, temporal
from alphaview_common.auth import Principal, get_principal
from alphaview_common.db import init_schema
from alphaview_common.web import create_app
from alphaview_discovery.config import get_settings
from alphaview_discovery.models import SCHEMA, Base, DiscoveryRun, Opportunity, RunStatus, engine, get_db
from alphaview_discovery.schemas import DiscoveryCreate, OpportunityOut, RunDetailOut, RunOut


@asynccontextmanager
async def lifespan(app):
    await init_schema(engine, Base, SCHEMA)
    app.state.temporal = await temporal.connect()
    yield


app = create_app("discovery", lifespan)


@app.get("/sources", tags=["discovery"])
async def list_sources() -> list[dict[str, str]]:
    return [{"id": k, "name": v} for k, v in contracts.SOURCES.items()]


@app.post("/discovery", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED, tags=["discovery"])
async def start_discovery(
    body: DiscoveryCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryRun:
    s = get_settings()
    sources = [x for x in dict.fromkeys(body.sources) if x in contracts.SOURCES]
    if not sources:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Choose sources from: {', '.join(contracts.SOURCES)}"
        )
    await ratelimit.enforce(f"runs:{principal.workspace_id}", limit=s.max_runs_per_hour, window_seconds=3600)

    run = DiscoveryRun(
        workspace_id=principal.workspace_id, created_by=principal.user_id, query=body.query.strip(), sources=sources
    )
    db.add(run)
    await db.commit()

    client: Client = request.app.state.temporal
    try:
        await client.start_workflow(
            contracts.DISCOVERY_WORKFLOW, str(run.id), id=f"discovery-{run.id}", task_queue=contracts.DISCOVERY_QUEUE
        )
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


@app.get("/opportunities/{opportunity_id}", response_model=OpportunityOut, tags=["discovery"])
async def get_opportunity(
    opportunity_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)
):
    opp = await db.get(Opportunity, opportunity_id)
    if opp is None or opp.workspace_id != principal.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    return opp
