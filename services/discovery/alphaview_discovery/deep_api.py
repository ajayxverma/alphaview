import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from alphaview_common import contracts
from alphaview_common.auth import Principal, get_principal
from alphaview_common.research import QUESTIONS, ResearchBudget, ResearchOptions
from alphaview_common.security import decode_token
from alphaview_discovery.budgets import locked_state, reserve
from alphaview_discovery.deep import permitted_domain
from alphaview_discovery.evidence import DocumentInput, ensure_state, require_run, store_document
from alphaview_discovery.evidence_models import ResearchCandidate, ResearchDocument, ResearchOperation
from alphaview_discovery.models import DiscoveryRun, Opportunity, get_db
from alphaview_discovery.research import near_duplicate

router = APIRouter(tags=["research"])


class ContinueResearch(BaseModel):
    additional_budget: ResearchBudget


class RequestPermit(BaseModel):
    index: int = Field(ge=1, le=40)
    url: str = Field(max_length=4096)


async def initialize_deep(session, run, options: ResearchOptions):
    run.research_config = options.model_dump(mode="json")
    await ensure_state(session, run)
    state = await locked_state(session, run.id, run.workspace_id)
    state.budget = options.budget.model_dump()
    state.usage = {"pages": 0, "queries": 0, "paid_calls": 0, "requests": 0, "budget_enforcement": "atomic"}
    state.deadline = datetime.now(UTC) + timedelta(seconds=options.budget.seconds)
    state.epoch = 1
    state.phase = "plan"
    state.round = 0
    state.stop_reason = None
    state.cancel_requested = False
    state.unresolved = list(QUESTIONS)
    run.status = "crawling"


async def owned_run(session, run_id, principal):
    run = await session.scalar(select(DiscoveryRun).where(DiscoveryRun.id == run_id,
        DiscoveryRun.workspace_id == principal.workspace_id).with_for_update())
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


async def continue_run(session, request, principal, run_id, budget, topic=None):
    run = await owned_run(session, run_id, principal)
    if run.status not in ("completed", "failed", "cancelled"):
        raise HTTPException(409, "Wait for the current run to stop before adding budget")
    was_deep = (run.research_config or {}).get("mode") == "deep"
    if not was_deep:
        options = ResearchOptions(mode="deep", budget=budget)
        await initialize_deep(session, run, options)
        run.sources = list(dict.fromkeys([*run.sources, "web"]))
    state = await locked_state(session, run.id, run.workspace_id)
    if was_deep:
        limits = {"seconds": 1800, "pages": 100, "queries": 30, "paid_calls": 30, "requests": 2000, "rounds": 5}
        combined = {name: state.budget.get(name, 0) + value for name, value in budget.model_dump().items()}
        if any(combined[name] > limit for name, limit in limits.items()):
            raise HTTPException(422, "Additional budget exceeds the per-run safety ceiling")
        state.budget = combined
        state.epoch += 1
        state.round += 1
        state.deadline = datetime.now(UTC) + timedelta(seconds=budget.seconds)
        state.cancel_requested = False
        state.stop_reason = None
        state.phase = "plan"
        state.complete = False
        run.status = "crawling"
    state.usage = {**state.usage, **({"topic": topic} if topic else {})}
    run.finished_at = None
    run.error = None
    epoch = state.epoch
    await session.commit()
    try:
        await request.app.state.temporal.start_workflow(contracts.DEEP_WORKFLOW, args=[str(run.id), epoch],
            id=f"deep-{run.id}-{epoch}", task_queue=contracts.DISCOVERY_QUEUE)
    except Exception as exc:
        run.status = "failed"
        run.error = "Continuation scheduling failed; collected evidence and reports are retained"
        state.phase = "scheduling_failed"
        await session.commit()
        raise HTTPException(503, "Unable to schedule continuation; evidence is retained") from exc
    return {"run_id": run.id, "epoch": epoch, "budget": state.budget}


@router.post("/discovery/{run_id}/continue", status_code=202)
async def continue_research(run_id: uuid.UUID, body: ContinueResearch, request: Request,
                           principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    return await continue_run(db, request, principal, run_id, body.additional_budget)


@router.post("/opportunities/{opportunity_id}/investigate", status_code=202)
async def investigate(opportunity_id: uuid.UUID, body: ContinueResearch, request: Request,
                      principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    opportunity = await db.scalar(select(Opportunity).where(Opportunity.id == opportunity_id, Opportunity.workspace_id == principal.workspace_id))
    if opportunity is None:
        raise HTTPException(404, "Opportunity not found")
    return await continue_run(db, request, principal, opportunity.run_id, body.additional_budget, ", ".join(opportunity.keywords)[:300])


@router.post("/discovery/{run_id}/cancel", status_code=202)
async def cancel_research(run_id: uuid.UUID, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    run = await owned_run(db, run_id, principal)
    if (run.research_config or {}).get("mode") != "deep":
        raise HTTPException(409, "Cancellation without deleting evidence is available for Deep runs")
    state = await locked_state(db, run.id, run.workspace_id)
    state.cancel_requested = True
    if run.status not in ("completed", "cancelled", "failed"):
        state.phase = "cancelling"
    await db.commit()
    return {"cancel_requested": True, "detail": "The current bounded operation may finish; no further requests will be authorized"}


async def service_operation(db, authorization):
    try:
        token = decode_token((authorization or "").removeprefix("Bearer "), purpose="research_ingest")
        operation = await db.scalar(select(ResearchOperation).where(
            ResearchOperation.id == uuid.UUID(token["operation"]), ResearchOperation.run_id == uuid.UUID(token["run"]),
            ResearchOperation.workspace_id == uuid.UUID(token["ws"]), ResearchOperation.kind.in_(["read", "search"]),
            ResearchOperation.status == "reserved"))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid research operation") from None
    if operation is None:
        raise HTTPException(401, "Research operation is not active")
    state = await locked_state(db, operation.run_id, operation.workspace_id)
    if operation.result.get("epoch", state.epoch) != state.epoch:
        raise HTTPException(401, "Research operation was superseded by a continuation")
    return operation


@router.post("/research/internal/request")
async def request_permit(body: RequestPermit, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    operation = await service_operation(db, authorization)
    run = await require_run(db, operation.run_id, operation.workspace_id)
    options = ResearchOptions.model_validate(run.research_config)
    if operation.kind == "read" and not permitted_domain(body.url, options):
        return {"allowed": False}
    permit = await reserve(db, run.id, run.workspace_id, f"{operation.id}:request:{body.index}", "request", {"requests": 1})
    allowed = permit is not None and permit.status == "reserved"
    if allowed:
        permit.status = "completed"
    await db.commit()
    return {"allowed": allowed}


@router.post("/research/internal/document")
async def ingest_document(document: DocumentInput, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    operation = await service_operation(db, authorization)
    if operation.kind != "read":
        raise HTTPException(401, "Document ingestion requires an authorized read")
    run = await require_run(db, operation.run_id, operation.workspace_id)
    await locked_state(db, run.id, run.workspace_id)
    if document.requested_url != operation.result["url"] or not permitted_domain(document.final_url, ResearchOptions.model_validate(run.research_config)):
        raise HTTPException(422, "Document does not match its authorized read")
    existing = list(await db.scalars(select(ResearchDocument).where(ResearchDocument.run_id == run.id,
        ResearchDocument.workspace_id == run.workspace_id).limit(100)))
    duplicate = next((item for item in existing if near_duplicate(item.text, document.text)), None)
    if duplicate:
        return {"outcome": "duplicate", "document_id": str(duplicate.id)}
    document.provenance = {**document.provenance, "question_id": operation.result["question_id"], "operation_id": str(operation.id)}
    document_id = await store_document(db, run.id, run.workspace_id, document)
    parent = await db.get(ResearchCandidate, uuid.UUID(operation.result["candidate_id"]))
    if parent and parent.depth < 2:
        for url in document.provenance.get("links", [])[:2]:
            if urlsplit(url).hostname != urlsplit(document.final_url).hostname:
                continue
            key = hashlib.sha256(f"link:{url}:{parent.question_id}".encode()).hexdigest()
            await db.execute(insert(ResearchCandidate).values(id=uuid.uuid5(run.id, key), run_id=run.id, workspace_id=run.workspace_id,
                key=key, url=url, question_id=parent.question_id, query=parent.query, provider="supporting_link", depth=parent.depth + 1,
                title="Supporting page", priority=0.5).on_conflict_do_nothing(constraint="uq_candidate_key"))
    await db.commit()
    return {"outcome": "fetched", "document_id": str(document_id)}