import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0002_research_evidence"
down_revision = "0001_quick_baseline"
branch_labels = None
depends_on = None


def run_columns():
    return [sa.Column("run_id", pg.UUID(), nullable=False), sa.Column("workspace_id", pg.UUID(), nullable=False)]


def timestamp(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade():
    op.add_column("discovery_runs", sa.Column("research_config", pg.JSONB(), nullable=True), schema="discovery")
    op.create_unique_constraint("uq_run_workspace", "discovery_runs", ["id", "workspace_id"], schema="discovery")
    op.create_table("research_states", *run_columns(),
        sa.Column("phase", sa.String(40), nullable=False, server_default="initial"),
        sa.Column("round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planner", sa.String(40), nullable=False, server_default="deterministic"),
        sa.Column("retrieval", sa.String(40), nullable=False, server_default="lexical_only"),
        sa.Column("budget", pg.JSONB(), nullable=False),
        sa.Column("usage", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("coverage", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("unresolved", pg.JSONB(), nullable=False, server_default="[]"),
        sa.Column("stop_reason", sa.String(80)), sa.Column("complete", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default="false"),
        timestamp("updated_at"), sa.PrimaryKeyConstraint("run_id"),
        sa.ForeignKeyConstraint(["run_id", "workspace_id"], ["discovery.discovery_runs.id", "discovery.discovery_runs.workspace_id"], ondelete="CASCADE"),
        schema="discovery")
    op.create_table("research_candidates", sa.Column("id", pg.UUID(), primary_key=True), *run_columns(),
        sa.Column("key", sa.String(64), nullable=False), sa.Column("url", sa.Text(), nullable=False),
        sa.Column("question_id", sa.String(40), nullable=False), sa.Column("query", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(60), nullable=False), sa.Column("position", sa.Integer()),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""), timestamp("retrieved_at"),
        sa.Column("priority", sa.Float(), nullable=False, server_default="0"),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outcome", sa.String(40), nullable=False, server_default="pending"),
        sa.UniqueConstraint("run_id", "workspace_id", "key", name="uq_candidate_key"),
        sa.ForeignKeyConstraint(["run_id", "workspace_id"], ["discovery.discovery_runs.id", "discovery.discovery_runs.workspace_id"], ondelete="CASCADE"), schema="discovery")
    op.create_table("research_documents", sa.Column("id", pg.UUID(), primary_key=True), *run_columns(),
        sa.Column("requested_url", sa.Text(), nullable=False), sa.Column("final_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text()), sa.Column("title", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(253), nullable=False), sa.Column("source", sa.String(60), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False), sa.Column("language", sa.String(10), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)), timestamp("retrieved_at"),
        sa.Column("date_uncertainty", sa.String(40), nullable=False), sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tables", pg.JSONB(), nullable=False, server_default="[]"), sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extraction_method", sa.String(60), nullable=False), sa.Column("provenance", pg.JSONB(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_document_workspace"),
        sa.UniqueConstraint("run_id", "workspace_id", "content_hash", name="uq_document_content"),
        sa.ForeignKeyConstraint(["run_id", "workspace_id"], ["discovery.discovery_runs.id", "discovery.discovery_runs.workspace_id"], ondelete="CASCADE"), schema="discovery")
    op.create_table("research_passages", sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("document_id", pg.UUID(), nullable=False), sa.Column("workspace_id", pg.UUID(), nullable=False),
        sa.Column("key", sa.String(64), nullable=False), sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("search_vector", pg.TSVECTOR(), sa.Computed("to_tsvector('simple', text)", persisted=True)),
        sa.UniqueConstraint("document_id", "key", name="uq_passage_key"),
        sa.ForeignKeyConstraint(["document_id", "workspace_id"], ["discovery.research_documents.id", "discovery.research_documents.workspace_id"], ondelete="CASCADE"), schema="discovery")
    op.create_index("ix_research_passage_search", "research_passages", ["search_vector"], schema="discovery", postgresql_using="gin")
    op.create_table("research_attempts", sa.Column("id", pg.UUID(), primary_key=True), *run_columns(),
        sa.Column("key", sa.String(64), nullable=False), sa.Column("source", sa.String(60), nullable=False),
        sa.Column("query", sa.Text(), nullable=False), sa.Column("question_id", sa.String(40)),
        sa.Column("requested_url", sa.Text()), sa.Column("final_url", sa.Text()),
        sa.Column("outcome", sa.String(40), nullable=False), sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False, server_default="0"), timestamp("retrieved_at"),
        sa.UniqueConstraint("run_id", "workspace_id", "key", name="uq_attempt_key"),
        sa.ForeignKeyConstraint(["run_id", "workspace_id"], ["discovery.discovery_runs.id", "discovery.discovery_runs.workspace_id"], ondelete="CASCADE"), schema="discovery")
    op.create_table("research_claims", sa.Column("id", pg.UUID(), primary_key=True), *run_columns(),
        sa.Column("text", sa.Text(), nullable=False), sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("quotation", sa.Text(), nullable=False), sa.Column("document_id", pg.UUID()), sa.Column("passage_id", pg.UUID()),
        sa.Column("status", sa.String(40), nullable=False), sa.Column("contradictions", pg.JSONB(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(["run_id", "workspace_id"], ["discovery.discovery_runs.id", "discovery.discovery_runs.workspace_id"], ondelete="CASCADE"), schema="discovery")
    op.create_table("research_versions", sa.Column("id", pg.UUID(), primary_key=True), *run_columns(),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("report", pg.JSONB(), nullable=False), timestamp("created_at"),
        sa.UniqueConstraint("run_id", "version", name="uq_research_version"),
        sa.ForeignKeyConstraint(["run_id", "workspace_id"], ["discovery.discovery_runs.id", "discovery.discovery_runs.workspace_id"], ondelete="CASCADE"), schema="discovery")
    for table in ("research_states", "research_candidates", "research_documents", "research_attempts", "research_claims", "research_versions"):
        op.create_index(f"ix_{table}_workspace_run", table, ["workspace_id", "run_id"], schema="discovery")


def downgrade():
    for table in ("research_versions", "research_claims", "research_attempts", "research_passages", "research_documents", "research_candidates", "research_states"):
        op.drop_table(table, schema="discovery")
    op.drop_constraint("uq_run_workspace", "discovery_runs", schema="discovery", type_="unique")
    op.drop_column("discovery_runs", "research_config", schema="discovery")