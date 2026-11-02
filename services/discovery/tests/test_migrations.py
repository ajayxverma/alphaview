import io

from alembic import command
from alembic.script import ScriptDirectory

from alphaview_discovery.migrate import migration_config


def test_research_migrations_have_one_head_and_generate_workspace_safe_ddl():
    config = migration_config()
    assert ScriptDirectory.from_config(config).get_heads() == ["0003_deep_operations"]
    output = io.StringIO()
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE IF NOT EXISTS discovery.discovery_runs" in sql
    assert "FOREIGN KEY(document_id, workspace_id)" in sql
    assert "to_tsvector('simple', text)" in sql
    assert "CREATE INDEX ix_research_passage_search" in sql
    assert "CREATE TABLE discovery.research_attempts" in sql
    assert "CREATE TABLE discovery.research_versions" in sql