import pytest
from spesometro_db import async_url, create_engine


def test_url_postgresql_diventa_asyncpg() -> None:
    url = async_url("postgresql://u:p@host:5432/db")
    assert url.drivername == "postgresql+asyncpg"
    assert url.port == 5432


def test_pool_size_massimo_cinque() -> None:
    engine = create_engine("postgresql://u:p@host:5432/db", pool_size=5)
    assert engine.pool.size() == 5
    with pytest.raises(ValueError):
        create_engine("postgresql://u:p@host:5432/db", pool_size=6)
