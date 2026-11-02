from alembic import op

revision = "0001_quick_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS discovery")
    op.execute("""CREATE TABLE IF NOT EXISTS discovery.discovery_runs (
        id UUID PRIMARY KEY, workspace_id UUID NOT NULL, created_by UUID,
        query VARCHAR(300) NOT NULL, sources JSON NOT NULL, geo JSON,
        status VARCHAR(20) NOT NULL, signal_count INTEGER NOT NULL, error TEXT,
        created_at TIMESTAMPTZ NOT NULL, finished_at TIMESTAMPTZ
    )""")
    op.execute("ALTER TABLE discovery.discovery_runs ADD COLUMN IF NOT EXISTS geo JSON")
    op.execute("""CREATE TABLE IF NOT EXISTS discovery.opportunities (
        id UUID PRIMARY KEY, run_id UUID NOT NULL REFERENCES discovery.discovery_runs(id) ON DELETE CASCADE,
        workspace_id UUID NOT NULL, title VARCHAR(200) NOT NULL, cluster_label VARCHAR(200) NOT NULL,
        keywords JSON NOT NULL, gap_score FLOAT NOT NULL, confidence FLOAT NOT NULL,
        metrics JSON NOT NULL, evidence JSON NOT NULL, strategy JSON NOT NULL, created_at TIMESTAMPTZ NOT NULL
    )""")
    for table, columns in {"discovery_runs": ("workspace_id", "created_at"),
                           "opportunities": ("workspace_id", "run_id", "gap_score")}.items():
        for column in columns:
            op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON discovery.{table} ({column})")


def downgrade():
    pass