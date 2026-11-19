"""La vista `price_observation`: l'unico punto da cui i prezzi unitari escono (ADR 0006)."""

import uuid
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

import asyncpg
from alembic import command
from alembic.config import Config

Sql = Callable[..., list[asyncpg.Record]]

COLONNE = [
    "user_id",
    "group_id",
    "product_id",
    "catena",
    "data",
    "prezzo_unitario",
    "fonte",
    "promo",
]


def _utente_e_gruppo(sql: Sql, unita_base: str) -> tuple[uuid.UUID, uuid.UUID]:
    uid, gid = uuid.uuid4(), uuid.uuid4()
    sql("INSERT INTO app_user (id) VALUES ($1)", uid)
    sql(
        "INSERT INTO product_group (id, user_id, nome, unita_base, tipo_durata)"
        " VALUES ($1, $2, 'g', $3, 'non_deperibile')",
        gid,
        uid,
        unita_base,
    )
    return uid, gid


def _prodotto(
    sql: Sql,
    uid: uuid.UUID,
    gid: uuid.UUID | None,
    *,
    vendita: str = "pezzo",
    dimensione_base: str | None = "1",
    unita_base: str = "L",
    stato: str = "auto",
) -> uuid.UUID:
    pid = uuid.uuid4()
    sql(
        "INSERT INTO product (id, user_id, nome, group_id, unita_di_vendita, dimensione_base,"
        " unita_base, fonte, stato) VALUES ($1, $2, 'p', $3, $4, $5::numeric, $6, 'scontrino', $7)",
        pid,
        uid,
        gid,
        vendita,
        dimensione_base,
        unita_base,
        stato,
    )
    return pid


def _riga_scontrino(
    sql: Sql,
    uid: uuid.UUID,
    pid: uuid.UUID,
    quantita: str,
    prezzo: str,
    *,
    sconto: str = "0",
    minuto: int = 30,
    stato: str = "auto",
) -> None:
    rid = uuid.uuid4()
    sql(
        "INSERT INTO receipt (id, user_id, data_ora, catena, totale)"
        " VALUES ($1, $2, $3, 'lidl', $4::numeric)",
        rid,
        uid,
        datetime(2026, 11, 10, 18, minuto),
        prezzo,
    )
    sql(
        "INSERT INTO receipt_line (id, user_id, receipt_id, testo_grezzo, quantita, prezzo,"
        " sconto, product_id, fonte, stato)"
        " VALUES ($1, $2, $3, 'riga', $4::numeric, $5::numeric, $6::numeric, $7, 'scontrino', $8)",
        uuid.uuid4(),
        uid,
        rid,
        quantita,
        prezzo,
        sconto,
        pid,
        stato,
    )


def _offerta(sql: Sql, uid: uuid.UUID, pid: uuid.UUID, tipo: str, *, stato: str = "auto") -> None:
    fid = uuid.uuid4()
    sql(
        "INSERT INTO flyer (id, user_id, catena, validita_da, validita_a, tipo, sha256)"
        " VALUES ($1, $2, 'eurospin', $3, $4, $5, $6)",
        fid,
        uid,
        date(2026, 11, 16),
        date(2026, 11, 22),
        tipo,
        uuid.uuid4().hex,
    )
    sql(
        "INSERT INTO offer (id, user_id, flyer_id, testo_grezzo, product_id, prezzo_unitario,"
        " fonte, stato) VALUES ($1, $2, $3, 'offerta', $4, 1.2500, 'volantino', $5)",
        uuid.uuid4(),
        uid,
        fid,
        pid,
        stato,
    )


def _osservazioni(sql: Sql, uid: uuid.UUID) -> list[asyncpg.Record]:
    return sql("SELECT * FROM price_observation WHERE user_id = $1", uid)


def test_la_vista_espone_esattamente_le_colonne_previste(migrated: Config, sql: Sql) -> None:
    righe = sql(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = 'price_observation'"
        " ORDER BY ordinal_position"
    )
    assert [r["column_name"] for r in righe] == COLONNE


def test_latte_a_pezzo_6x1L_a_5_34_vale_0_89_al_litro(migrated: Config, sql: Sql) -> None:
    uid, gid = _utente_e_gruppo(sql, "L")
    pid = _prodotto(sql, uid, gid, dimensione_base="6")  # confezione 6 x 1 L = 6 L
    _riga_scontrino(sql, uid, pid, "1", "5.34")
    [riga] = _osservazioni(sql, uid)
    assert round(riga["prezzo_unitario"], 2) == Decimal("0.89")
    assert (riga["fonte"], riga["promo"], riga["catena"]) == ("scontrino", False, "lidl")
    assert (riga["group_id"], riga["product_id"]) == (gid, pid)
    assert riga["data"] == date(2026, 11, 10)


def test_banane_a_peso_variabile_1_234_kg_a_2_09_valgono_1_69_al_kg(
    migrated: Config, sql: Sql
) -> None:
    uid, gid = _utente_e_gruppo(sql, "kg")
    pid = _prodotto(sql, uid, gid, vendita="peso_variabile", dimensione_base=None, unita_base="kg")
    _riga_scontrino(sql, uid, pid, "1.234", "2.09")
    [riga] = _osservazioni(sql, uid)
    assert round(riga["prezzo_unitario"], 2) == Decimal("1.69")


def test_lo_sconto_della_riga_scende_dal_prezzo_e_marca_promo(migrated: Config, sql: Sql) -> None:
    uid, gid = _utente_e_gruppo(sql, "L")
    pid = _prodotto(sql, uid, gid, dimensione_base="6")
    _riga_scontrino(sql, uid, pid, "1", "5.34", sconto="0.60")
    [riga] = _osservazioni(sql, uid)
    assert round(riga["prezzo_unitario"], 2) == Decimal("0.79")
    assert riga["promo"] is True


def test_riga_rifiutata_non_compare(migrated: Config, sql: Sql) -> None:
    uid, gid = _utente_e_gruppo(sql, "L")
    pid = _prodotto(sql, uid, gid, dimensione_base="6")
    _riga_scontrino(sql, uid, pid, "1", "5.34", stato="rifiutato")
    _offerta(sql, uid, pid, "settimanale", stato="rifiutato")
    assert _osservazioni(sql, uid) == []


def test_prodotto_senza_gruppo_o_rifiutato_non_compare(migrated: Config, sql: Sql) -> None:
    uid, gid = _utente_e_gruppo(sql, "L")
    senza_gruppo = _prodotto(sql, uid, None, dimensione_base="6")
    rifiutato = _prodotto(sql, uid, gid, dimensione_base="6", stato="rifiutato")
    for minuto, pid in enumerate((senza_gruppo, rifiutato)):
        _riga_scontrino(sql, uid, pid, "1", "5.34", minuto=minuto)
        _offerta(sql, uid, pid, "settimanale")
    assert _osservazioni(sql, uid) == []


def test_offerta_di_un_volantino_catalogo_ha_promo_falso(migrated: Config, sql: Sql) -> None:
    uid, gid = _utente_e_gruppo(sql, "L")
    pid = _prodotto(sql, uid, gid)
    _offerta(sql, uid, pid, "catalogo")
    [riga] = _osservazioni(sql, uid)
    assert riga["promo"] is False
    assert (riga["fonte"], riga["catena"]) == ("volantino", "eurospin")
    assert riga["data"] == date(2026, 11, 16)
    assert riga["prezzo_unitario"] == Decimal("1.25")


def test_offerta_di_un_volantino_settimanale_ha_promo_vero(migrated: Config, sql: Sql) -> None:
    uid, gid = _utente_e_gruppo(sql, "L")
    pid = _prodotto(sql, uid, gid)
    _offerta(sql, uid, pid, "settimanale")
    [riga] = _osservazioni(sql, uid)
    assert riga["promo"] is True


def test_downgrade_rimuove_la_vista(migrated: Config, sql: Sql) -> None:
    command.downgrade(migrated, "base")
    assert sql("SELECT 1 FROM pg_views WHERE viewname = 'price_observation'") == []


def test_alembic_check_non_vede_la_vista_come_differenza(migrated: Config) -> None:
    command.check(migrated)
