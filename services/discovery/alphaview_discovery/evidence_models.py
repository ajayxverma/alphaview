import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Computed, DateTime, Float, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from alphaview_discovery.models import Base


def run_reference():
    return ForeignKeyConstraint(["run_id", "workspace_id"],
        ["discovery.discovery_runs.id", "discovery.discovery_runs.workspace_id"], ondelete="CASCADE")


class ResearchState(Base):
    __tablename__ = "research_states"
    __table_args__ = (run_reference(),)
    run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[uuid.UUID]
    phase: Mapped[str] = mapped_column(String(40), default="initial")
    round: Mapped[int] = mapped_column(Integer, default=0)
    planner: Mapped[str] = mapped_column(String(40), default="deterministic")
    retrieval: Mapped[str] = mapped_column(String(40), default="lexical_only")
    budget: Mapped[dict] = mapped_column(JSONB)
    usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    coverage: Mapped[dict] = mapped_column(JSONB, default=dict)
    unresolved: Mapped[list] = mapped_column(JSONB, default=list)
    stop_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    epoch: Mapped[int] = mapped_column(Integer, default=0)


class ResearchAttempt(Base):
    __tablename__ = "research_attempts"
    __table_args__ = (run_reference(), UniqueConstraint("run_id", "workspace_id", "key", name="uq_attempt_key"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(60))
    query: Mapped[str] = mapped_column(Text)
    question_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    requested_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ResearchDocument(Base):
    __tablename__ = "research_documents"
    __table_args__ = (run_reference(), UniqueConstraint("id", "workspace_id", name="uq_document_workspace"),
                     UniqueConstraint("run_id", "workspace_id", "content_hash", name="uq_document_content"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    requested_url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(253))
    source: Mapped[str] = mapped_column(String(60))
    document_type: Mapped[str] = mapped_column(String(40))
    language: Mapped[str] = mapped_column(String(10))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    date_uncertainty: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    tables: Mapped[list] = mapped_column(JSONB, default=list)
    content_hash: Mapped[str] = mapped_column(String(64))
    extraction_method: Mapped[str] = mapped_column(String(60))
    provenance: Mapped[dict] = mapped_column(JSONB)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)


class ResearchPassage(Base):
    __tablename__ = "research_passages"
    __table_args__ = (UniqueConstraint("document_id", "key", name="uq_passage_key"),
        ForeignKeyConstraint(["document_id", "workspace_id"],
            ["discovery.research_documents.id", "discovery.research_documents.workspace_id"], ondelete="CASCADE"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(64))
    offset: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[str] = mapped_column(TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True))


class ResearchCandidate(Base):
    __tablename__ = "research_candidates"
    __table_args__ = (run_reference(), UniqueConstraint("run_id", "workspace_id", "key", name="uq_candidate_key"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text)
    question_id: Mapped[str] = mapped_column(String(40))
    query: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(60))
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text, default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    priority: Mapped[float] = mapped_column(Float, default=0)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(String(40), default="pending")


class ResearchOperation(Base):
    __tablename__ = "research_operations"
    __table_args__ = (run_reference(), UniqueConstraint("run_id", "workspace_id", "key", name="uq_operation_key"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    key: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(30))
    cost: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30))
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ResearchClaim(Base):
    __tablename__ = "research_claims"
    __table_args__ = (run_reference(),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40))
    quotation: Mapped[str] = mapped_column(Text)
    document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    passage_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    contradictions: Mapped[list] = mapped_column(JSONB, default=list)


class ResearchVersion(Base):
    __tablename__ = "research_versions"
    __table_args__ = (run_reference(), UniqueConstraint("run_id", "version", name="uq_research_version"))
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID]
    workspace_id: Mapped[uuid.UUID]
    version: Mapped[int] = mapped_column(Integer)
    report: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))