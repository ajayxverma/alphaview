import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0003_deep_operations"
down_revision = "0002_research_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("research_states", sa.Column("deadline", sa.DateTime(timezone=True)), schema="discovery")
    op.add_column("research_states", sa.Column("epoch", sa.Integer(), nullable=False, server_default="0"), schema="discovery")
    op.create_table("research_operations",
        sa.Column("id", pg.UUID(), primary_key=True), sa.Column("run_id", pg.UUID(), nullable=False),
        sa.Column("workspace_id", pg.UUID(), nullable=False), sa.Column("key", sa.String(300), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False), sa.Column("cost", pg.JSONB(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("result", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "workspace_id", "key", name="uq_operation_key"),
        sa.ForeignKeyConstraint(["run_id", "workspace_id"],
            ["discovery.discovery_runs.id", "discovery.discovery_runs.workspace_id"], ondelete="CASCADE"), schema="discovery")


def downgrade():
    op.drop_table("research_operations", schema="discovery")
    op.drop_column("research_states", "epoch", schema="discovery")
    op.drop_column("research_states", "deadline", schema="discovery")