import hashlib
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from alphaview_common.research import QUESTIONS, ResearchOptions
from alphaview_discovery.evidence_models import ResearchAttempt, ResearchDocument, ResearchPassage, ResearchState
from alphaview_discovery.models import DiscoveryRun
from alphaview_discovery.research import passages


class DocumentInput(BaseModel):
    requested_url: str = Field(max_length=4096)
    final_url: str = Field(max_length=4096)
    title: str = Field(max_length=500)
    source: str = Field(max_length=60)
    document_type: str = Field(pattern=r"^(article|product|pricing|documentation|discussion|reference)$")
    text: str = Field(min_length=1, max_length=64000)
    language: str = Field(default="en", pattern=r"^[a-z]{2}$")
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    canonical_url: str | None = Field(default=None, max_length=4096)
    extraction_method: str = Field(default="source_api", max_length=60)
    provenance: dict = Field(default_factory=dict)
    tables: list = Field(default_factory=list, max_length=20)
    truncated: bool = False

    @model_validator(mode="after")
    def validate_dates_and_urls(self):
        for url in (self.requested_url, self.final_url, self.canonical_url):
            if url is None:
                continue
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Evidence URLs must be HTTPS without embedded credentials")
        if self.canonical_url and urlsplit(self.canonical_url).hostname != urlsplit(self.final_url).hostname:
            raise ValueError("Canonical URL must belong to the fetched domain")
        for date in (self.published_at, self.retrieved_at):
            if date is not None and date.tzinfo is None:
                raise ValueError("Evidence timestamps must include timezone")
        return self


async def require_run(session, run_id: uuid.UUID, workspace_id: uuid.UUID) -> DiscoveryRun:
    run = await session.scalar(select(DiscoveryRun).where(DiscoveryRun.id == run_id, DiscoveryRun.workspace_id == workspace_id))
    if run is None:
        raise LookupError("Run not found")
    return run


async def ensure_state(session, run: DiscoveryRun) -> None:
    options = ResearchOptions.model_validate(run.research_config or {})
    await session.execute(insert(ResearchState).values(
        run_id=run.id, workspace_id=run.workspace_id, budget=options.budget.model_dump(),
        unresolved=list(QUESTIONS), planner="deterministic", retrieval="lexical_only",
        usage={"budget_enforcement": "legacy_quick"},
    ).on_conflict_do_nothing(index_elements=["run_id"]))


async def store_document(session, run_id: uuid.UUID, workspace_id: uuid.UUID, document: DocumentInput) -> uuid.UUID:
    await require_run(session, run_id, workspace_id)
    content_hash = hashlib.sha256(document.text.encode()).hexdigest()
    document_id = uuid.uuid5(run_id, content_hash)
    values = document.model_dump()
    values.update(id=document_id, run_id=run_id, workspace_id=workspace_id, content_hash=content_hash,
                  domain=urlsplit(document.final_url).hostname,
                  date_uncertainty="known" if document.published_at else "unknown")
    await session.execute(insert(ResearchDocument).values(**values).on_conflict_do_nothing(
        constraint="uq_document_content"))
    for passage in passages(document.text):
        await session.execute(insert(ResearchPassage).values(
            id=uuid.uuid5(document_id, passage["key"]), document_id=document_id, workspace_id=workspace_id,
            key=passage["key"], offset=passage["offset"], text=passage["text"],
        ).on_conflict_do_nothing(constraint="uq_passage_key"))
    return document_id


async def store_attempts(session, run_id: uuid.UUID, workspace_id: uuid.UUID, attempts: list[dict]) -> None:
    run = await require_run(session, run_id, workspace_id)
    await ensure_state(session, run)
    for attempt in attempts:
        values = {key: attempt.get(key) for key in ("source", "query", "requested_url", "final_url", "outcome")}
        values["source"] = values["source"] or "web"
        values["query"] = values["query"] or run.query
        key = hashlib.sha256(f"{values['source']}|{values['query']}|{values['requested_url']}".encode()).hexdigest()
        values.update(id=uuid.uuid5(run_id, key), run_id=run_id, workspace_id=workspace_id, key=key,
                      detail=attempt.get("detail", "")[:500], signal_count=attempt.get("signal_count", 0))
        await session.execute(insert(ResearchAttempt).values(**values).on_conflict_do_update(
            constraint="uq_attempt_key", set_={key: value for key, value in values.items() if key not in ("id", "key")}))


async def search_passages(session, run_id: uuid.UUID, workspace_id: uuid.UUID, query: str,
                          source: str | None = None, document_type: str | None = None,
                          date_from: datetime | None = None, date_to: datetime | None = None,
                          language: str | None = None, match_all: bool = True) -> list[dict]:
    await require_run(session, run_id, workspace_id)
    tsquery = func.plainto_tsquery("simple", query) if match_all else func.websearch_to_tsquery("simple", " OR ".join(query.split()))
    rank = func.ts_rank_cd(ResearchPassage.search_vector, tsquery).label("rank")
    statement = select(ResearchPassage.id, ResearchPassage.document_id, ResearchPassage.text, rank,
        ResearchDocument.title, ResearchDocument.final_url, ResearchDocument.source, ResearchDocument.document_type,
        ResearchDocument.published_at, ResearchDocument.date_uncertainty).join(ResearchDocument,
        (ResearchDocument.id == ResearchPassage.document_id) & (ResearchDocument.workspace_id == ResearchPassage.workspace_id)
    ).where(ResearchDocument.run_id == run_id, ResearchDocument.workspace_id == workspace_id,
            ResearchPassage.workspace_id == workspace_id, ResearchPassage.search_vector.op("@@")(tsquery))
    for field, value in ((ResearchDocument.source, source), (ResearchDocument.document_type, document_type),
                         (ResearchDocument.language, language)):
        if value:
            statement = statement.where(field == value)
    if date_from:
        statement = statement.where(ResearchDocument.published_at >= date_from)
    if date_to:
        statement = statement.where(ResearchDocument.published_at <= date_to)
    if not match_all:
        ranked = statement.add_columns(func.row_number().over(partition_by=ResearchPassage.document_id,
            order_by=(rank.desc(), ResearchPassage.id)).label("document_position")).subquery()
        statement = select(ranked).where(ranked.c.document_position <= 2).order_by(ranked.c.rank.desc()).limit(40)
    else:
        statement = statement.order_by(rank.desc(), ResearchPassage.id).limit(40)
    results = (await session.execute(statement)).mappings()
    return [dict(row) for row in results]