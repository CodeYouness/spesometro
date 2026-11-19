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
    assert {
        "app_user",
        "exclusion",
        "product_group",
        "product",
        "product_alias",
        "group_alternative",
    } <= nomi
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


def _nuovo_gruppo(sql: Sql, uid: uuid.UUID) -> uuid.UUID:
    gid = uuid.uuid4()
    sql(
        "INSERT INTO product_group (id, user_id, nome, unita_base, tipo_durata)"
        " VALUES ($1, $2, 'latte', 'L', 'scadenza_reale')",
        gid,
        uid,
    )
    return gid


def _nuovo_prodotto(sql: Sql, uid: uuid.UUID, gid: uuid.UUID | None = None) -> uuid.UUID:
    pid = uuid.uuid4()
    sql(
        "INSERT INTO product (id, user_id, nome, group_id, unita_di_vendita, fonte)"
        " VALUES ($1, $2, 'latte ps', $3, 'pezzo', 'umano')",
        pid,
        uid,
        gid,
    )
    return pid


_ALIAS = (
    "INSERT INTO product_alias (id, user_id, testo_grezzo, catena, product_id, fonte, stato)"
    " VALUES ($1, $2, 'LATTE PS', 'lidl', $3, 'scontrino', $4)"
)


def test_catalogo_con_prodotto_senza_gruppo_e_con_gruppo(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    _nuovo_prodotto(sql, uid)
    _nuovo_prodotto(sql, uid, _nuovo_gruppo(sql, uid))


def test_secondo_alias_non_rifiutato_respinto(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    pid = _nuovo_prodotto(sql, uid)
    sql(_ALIAS, uuid.uuid4(), uid, pid, "auto")
    with pytest.raises(asyncpg.UniqueViolationError):
        sql(_ALIAS, uuid.uuid4(), uid, pid, "rivisto")


def test_secondo_alias_accettato_se_il_primo_e_rifiutato(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    pid = _nuovo_prodotto(sql, uid)
    sql(_ALIAS, uuid.uuid4(), uid, pid, "rifiutato")
    sql(_ALIAS, uuid.uuid4(), uid, pid, "auto")


def test_alternativa_di_un_gruppo_con_se_stesso_respinta(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    gid = _nuovo_gruppo(sql, uid)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(
            "INSERT INTO group_alternative (id, user_id, group_a, group_b, fonte)"
            " VALUES ($1, $2, $3, $3, 'umano')",
            uuid.uuid4(),
            uid,
            gid,
        )


def test_alternativa_orientata_unica_ma_il_verso_opposto_e_ammesso(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    a, b = _nuovo_gruppo(sql, uid), _nuovo_gruppo(sql, uid)
    ins = (
        "INSERT INTO group_alternative (id, user_id, group_a, group_b, fonte)"
        " VALUES ($1, $2, $3, $4, 'umano')"
    )
    sql(ins, uuid.uuid4(), uid, a, b)
    sql(ins, uuid.uuid4(), uid, b, a)
    with pytest.raises(asyncpg.UniqueViolationError):
        sql(ins, uuid.uuid4(), uid, a, b)


def test_attributo_del_prodotto_fuori_dall_insieme_respinto(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(
            "INSERT INTO product (id, user_id, nome, unita_di_vendita, attributi, fonte)"
            " VALUES ($1, $2, 'x', 'pezzo', ARRAY['noci'], 'umano')",
            uuid.uuid4(),
            uid,
        )


def test_confidenza_fuori_da_0_1_respinta(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(
            "INSERT INTO product (id, user_id, nome, unita_di_vendita, fonte, confidenza)"
            " VALUES ($1, $2, 'x', 'pezzo', 'umano', 1.5)",
            uuid.uuid4(),
            uid,
        )


def test_cancellando_l_utente_spariscono_catalogo_e_alias(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    pid = _nuovo_prodotto(sql, uid, _nuovo_gruppo(sql, uid))
    sql(_ALIAS, uuid.uuid4(), uid, pid, "auto")
    sql("DELETE FROM app_user WHERE id = $1", uid)
    for tabella in ("product_group", "product", "product_alias"):
        assert sql(f"SELECT 1 FROM {tabella}") == []
