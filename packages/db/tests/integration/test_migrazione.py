"""Database migrato: ciclo di migrazione, RLS, estensioni e vincoli che respingono davvero."""

import uuid
from collections.abc import Callable

import asyncpg
import pytest
from alembic import command
from alembic.config import Config

Sql = Callable[..., list[asyncpg.Record]]


def test_ciclo_upgrade_downgrade_upgrade_e_check_senza_differenze(alembic_cfg: Config) -> None:
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    command.check(alembic_cfg)  # solleva CommandError se modelli e database divergono


def test_downgrade_base_lascia_il_database_vuoto(migrated: Config, sql: Sql) -> None:
    command.downgrade(migrated, "base")
    tabelle = sql(
        "SELECT tablename FROM pg_tables"
        " WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
    )
    assert tabelle == []


def test_rls_abilitata_su_ogni_tabella(migrated: Config, sql: Sql) -> None:
    righe = sql("SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public'")
    senza_rls = [r["tablename"] for r in righe if not r["rowsecurity"]]
    nomi = {r["tablename"] for r in righe}
    assert {"app_user", "exclusion"} <= nomi
    assert senza_rls == [] or senza_rls == ["alembic_version"]


def test_pg_trgm_attiva(migrated: Config, sql: Sql) -> None:
    assert sql("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")


def _nuovo_utente(sql: Sql) -> uuid.UUID:
    uid = uuid.uuid4()
    sql("INSERT INTO app_user (id) VALUES ($1)", uid)
    return uid


def test_seconda_esclusione_con_lo_stesso_attributo_respinta(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    sql("INSERT INTO exclusion (user_id, attributo, tipo) VALUES ($1, 'glutine', 'dieta')", uid)
    with pytest.raises(asyncpg.UniqueViolationError):
        sql(
            "INSERT INTO exclusion (user_id, attributo, tipo) VALUES ($1, 'glutine', 'allergia')",
            uid,
        )


def test_attributo_o_tipo_fuori_dall_insieme_respinti(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    with pytest.raises(asyncpg.CheckViolationError):
        sql("INSERT INTO exclusion (user_id, attributo, tipo) VALUES ($1, 'noci', 'dieta')", uid)
    with pytest.raises(asyncpg.CheckViolationError):
        sql("INSERT INTO exclusion (user_id, attributo, tipo) VALUES ($1, 'glutine', 'gusto')", uid)


def test_catena_fuori_dall_insieme_respinta_su_user(migrated: Config, sql: Sql) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        sql("INSERT INTO app_user (id, carte_fedelta) VALUES ($1, ARRAY['conad'])", uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError):
        sql("INSERT INTO app_user (id, catena_abituale) VALUES ($1, 'conad')", uuid.uuid4())


def test_preferenze_di_default(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    riga = sql(
        "SELECT risparmio_minimo_per_negozio, max_negozi, carte_fedelta"
        " FROM app_user WHERE id = $1",
        uid,
    )[0]
    assert float(riga["risparmio_minimo_per_negozio"]) == 5.0
    assert riga["max_negozi"] == 2
    assert riga["carte_fedelta"] == []


def test_cancellando_l_utente_spariscono_le_sue_righe(migrated: Config, sql: Sql) -> None:
    uid, altro = _nuovo_utente(sql), _nuovo_utente(sql)
    for u in (uid, altro):
        sql("INSERT INTO exclusion (user_id, attributo, tipo) VALUES ($1, 'carne', 'dieta')", u)
    sql("DELETE FROM app_user WHERE id = $1", uid)
    rimaste = sql("SELECT user_id FROM exclusion")
    assert [r["user_id"] for r in rimaste] == [altro]
