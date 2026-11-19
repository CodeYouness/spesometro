"""Postgres usa e getta in Docker per i test `integration` (mai Supabase: ADR 0001)."""

import asyncio
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"
IMMAGINE = "postgres:17"
PASSWORD = "test"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if Path(item.fspath).parent == Path(__file__).parent:
            item.add_marker(pytest.mark.integration)


def _docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture(scope="session")
def postgres_base_url() -> Iterator[str]:
    """URL `postgresql://` del server usa e getta (database `postgres`)."""
    nome = f"spesometro-test-{uuid.uuid4().hex[:8]}"
    _docker(
        "run", "-d", "--rm", "--name", nome,
        "-e", f"POSTGRES_PASSWORD={PASSWORD}",
        "-p", "127.0.0.1::5432",
        IMMAGINE,
    )  # fmt: skip
    try:
        porta = _docker("port", nome, "5432/tcp").splitlines()[0].rsplit(":", 1)[1]
        url = f"postgresql://postgres:{PASSWORD}@127.0.0.1:{porta}"
        scadenza = time.monotonic() + 60
        while True:
            try:
                asyncio.run(_execute(f"{url}/postgres", "SELECT 1"))
                break
            except (OSError, asyncpg.PostgresError):
                if time.monotonic() > scadenza:
                    raise
                time.sleep(0.5)
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", nome], capture_output=True)


async def _execute(url: str, sql: str, *args: Any) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(url)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


@pytest.fixture
def database_url(postgres_base_url: str) -> str:
    """Database vuoto e nuovo per ogni test."""
    nome = f"t_{uuid.uuid4().hex[:12]}"
    asyncio.run(_execute(f"{postgres_base_url}/postgres", f"CREATE DATABASE {nome}"))
    return f"{postgres_base_url}/{nome}"


@pytest.fixture
def sql(database_url: str) -> Callable[..., list[asyncpg.Record]]:
    def esegui(query: str, *args: Any) -> list[asyncpg.Record]:
        return asyncio.run(_execute(database_url, query, *args))

    return esegui


@pytest.fixture
def alembic_cfg(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", database_url)
    return Config(str(ALEMBIC_INI))


@pytest.fixture
def migrated(alembic_cfg: Config) -> Config:
    command.upgrade(alembic_cfg, "head")
    return alembic_cfg
