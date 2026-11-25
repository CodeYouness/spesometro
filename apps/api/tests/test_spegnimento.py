"""Allo spegnimento dell'app l'engine condiviso viene chiuso."""

from fastapi.testclient import TestClient
from spesometro_api.main import app
from sqlalchemy.ext.asyncio import AsyncEngine


def test_l_engine_viene_chiuso_allo_spegnimento(monkeypatch) -> None:
    chiusure: list[AsyncEngine] = []
    originale = AsyncEngine.dispose

    async def spia(self: AsyncEngine, close: bool = True) -> None:
        chiusure.append(self)
        await originale(self, close)

    monkeypatch.setattr(AsyncEngine, "dispose", spia)

    with TestClient(app):
        assert not chiusure
    assert len(chiusure) == 1
