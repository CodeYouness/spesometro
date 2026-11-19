"""Motore e sessioni async da `DATABASE_URL` (session pooler, porta 5432: ADR 0001)."""

import os

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

POOL_SIZE_MAX = 5


def async_url(database_url: str) -> URL:
    """Converte `postgresql://…` nel dialetto asyncpg."""
    url = make_url(database_url)
    if url.drivername in {"postgresql", "postgres"}:
        url = url.set(drivername="postgresql+asyncpg")
    return url


def database_url_from_env() -> str:
    try:
        return os.environ["DATABASE_URL"]
    except KeyError:
        raise RuntimeError("DATABASE_URL non impostata") from None


def create_engine(
    database_url: str | None = None, *, pool_size: int = POOL_SIZE_MAX
) -> AsyncEngine:
    if not 1 <= pool_size <= POOL_SIZE_MAX:
        raise ValueError(f"pool_size deve essere tra 1 e {POOL_SIZE_MAX}")
    url = async_url(database_url or database_url_from_env())
    return create_async_engine(url, pool_size=pool_size, max_overflow=0, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
