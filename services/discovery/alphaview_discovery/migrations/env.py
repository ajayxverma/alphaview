from alembic import context


def migrate(connection):
    context.configure(connection=connection, version_table_schema="discovery", include_schemas=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url="postgresql://", literal_binds=True, dialect_opts={"paramstyle": "named"},
                      version_table_schema="discovery")
    with context.begin_transaction():
        context.run_migrations()
else:
    migrate(context.config.attributes["connection"])