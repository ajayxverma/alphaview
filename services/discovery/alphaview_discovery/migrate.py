from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text


def migration_config(connection=None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


async def upgrade_database(engine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('discovery'))"))
        await connection.execute(text("CREATE SCHEMA IF NOT EXISTS discovery"))
        await connection.run_sync(lambda sync: command.upgrade(migration_config(sync), "head"))