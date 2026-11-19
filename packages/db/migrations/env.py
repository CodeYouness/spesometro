"""Alembic async: legge `DATABASE_URL` (postgresql://… sul pooler 5432) e usa asyncpg."""

import asyncio

from alembic import context
from spesometro_db import Base, async_url
from spesometro_db import models as _models  # noqa: F401  (registra le tabelle nei metadati)
from spesometro_db.engine import database_url_from_env
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=async_url(database_url_from_env()).render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(async_url(database_url_from_env()), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
