"""Comando del profilo `User` e verifica di ammissione (ticket login lato server, 01)."""

import asyncio
import uuid
from collections.abc import Callable

import pytest
from spesometro_db import create_engine, create_session_factory
from spesometro_db.profilo import main, utente_ammesso

Sql = Callable[..., list]


@pytest.fixture
def db(migrated, database_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("DATABASE_URL", database_url)
    return database_url


def _ammesso(database_url: str, user_id: uuid.UUID) -> bool:
    async def run() -> bool:
        engine = create_engine(database_url, pool_size=1)
        try:
            return await utente_ammesso(create_session_factory(engine), user_id)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_crea_il_profilo_con_i_valori_predefiniti(db, sql: Sql, capsys) -> None:
    uid = uuid.uuid4()
    assert main([str(uid)]) == 0
    righe = sql(
        "SELECT carte_fedelta, catena_abituale, risparmio_minimo_per_negozio, max_negozi"
        " FROM app_user WHERE id = $1",
        uid,
    )
    assert len(righe) == 1
    assert righe[0]["carte_fedelta"] == []
    assert righe[0]["catena_abituale"] is None
    assert str(righe[0]["risparmio_minimo_per_negozio"]) == "5.00"
    assert righe[0]["max_negozi"] == 2
    assert "creato" in capsys.readouterr().out.lower()


def test_seconda_esecuzione_non_cambia_nulla(db, sql: Sql, capsys) -> None:
    uid = uuid.uuid4()
    main([str(uid)])
    sql("UPDATE app_user SET max_negozi = 3 WHERE id = $1", uid)
    capsys.readouterr()
    assert main([str(uid)]) == 0
    assert "esiste già" in capsys.readouterr().out
    assert sql("SELECT max_negozi FROM app_user WHERE id = $1", uid)[0]["max_negozi"] == 3
    assert sql("SELECT count(*) AS n FROM app_user")[0]["n"] == 1


def test_identificativo_non_uuid_e_un_errore(db, sql: Sql, capsys) -> None:
    assert main(["non-un-uuid"]) != 0
    assert "uuid" in capsys.readouterr().err.lower()
    assert sql("SELECT count(*) AS n FROM app_user")[0]["n"] == 0


def test_ammissione_trova_il_profilo_creato_e_non_uno_sconosciuto(db) -> None:
    uid = uuid.uuid4()
    assert _ammesso(db, uid) is False
    main([str(uid)])
    assert _ammesso(db, uid) is True
    assert _ammesso(db, uuid.uuid4()) is False
