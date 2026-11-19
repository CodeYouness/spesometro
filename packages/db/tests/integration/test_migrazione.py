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
        "flyer",
        "offer",
        "receipt",
        "receipt_line",
    } <= nomi
    assert senza_rls == [] or senza_rls == ["alembic_version"]


def test_downgrade_lascia_pg_trgm(migrated: Config, sql: Sql) -> None:
    command.downgrade(migrated, "base")
    assert sql("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")


SCHEMA_PG_TRGM = (
    "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace"
    " WHERE e.extname = 'pg_trgm'"
)


def test_pg_trgm_attiva_nello_schema_extensions(migrated: Config, sql: Sql) -> None:
    # L'advisor di Supabase segnala le estensioni in `public` (lint 0014).
    assert [r["nspname"] for r in sql(SCHEMA_PG_TRGM)] == ["extensions"]


def test_upgrade_sposta_pg_trgm_lasciata_in_public(alembic_cfg: Config, sql: Sql) -> None:
    # Il downgrade non toglie l'estensione: se una versione precedente l'ha messa in `public`,
    # l'upgrade la porta in `extensions`.
    sql("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")
    command.upgrade(alembic_cfg, "head")
    assert [r["nspname"] for r in sql(SCHEMA_PG_TRGM)] == ["extensions"]


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


_FLYER = (
    "INSERT INTO flyer (id, user_id, catena, validita_da, validita_a, tipo, sha256)"
    " VALUES ($1, $2, 'lidl', '2026-11-16', '2026-11-22', 'settimanale', $3)"
)
_RECEIPT = (
    "INSERT INTO receipt (id, user_id, data_ora, catena, totale)"
    " VALUES ($1, $2, '2026-11-18 17:42:00', $3, 5.34)"
)


def test_secondo_volantino_con_lo_stesso_sha256_respinto_per_lo_stesso_utente(
    migrated: Config, sql: Sql
) -> None:
    uid, altro = _nuovo_utente(sql), _nuovo_utente(sql)
    sql(_FLYER, uuid.uuid4(), uid, "abc")
    with pytest.raises(asyncpg.UniqueViolationError):
        sql(_FLYER, uuid.uuid4(), uid, "abc")
    sql(_FLYER, uuid.uuid4(), altro, "abc")  # un altro utente può avere lo stesso file


def test_tipo_di_volantino_fuori_dall_insieme_respinto(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(_FLYER.replace("'settimanale'", "'mensile'"), uuid.uuid4(), uid, "abc")


def test_secondo_scontrino_con_la_stessa_chiave_naturale_respinto(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    sql(_RECEIPT, uuid.uuid4(), uid, "lidl")
    with pytest.raises(asyncpg.UniqueViolationError):
        sql(_RECEIPT, uuid.uuid4(), uid, "lidl")
    sql(_RECEIPT, uuid.uuid4(), uid, "coop")  # catena diversa: scontrino diverso


def test_scontrino_di_catena_altra_accettato(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    sql(_RECEIPT, uuid.uuid4(), uid, "altra")
    with pytest.raises(asyncpg.CheckViolationError):
        sql(_RECEIPT, uuid.uuid4(), uid, "conad")


def test_offerta_e_riga_di_scontrino_con_provenienza_e_numeri_esatti(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    fid, rid = uuid.uuid4(), uuid.uuid4()
    sql(_FLYER, fid, uid, "abc")
    sql(_RECEIPT, rid, uid, "lidl")
    sql(
        "INSERT INTO offer (id, user_id, flyer_id, testo_grezzo, prezzo_unitario, unita, fonte)"
        " VALUES ($1, $2, $3, 'LATTE 1L', 0.8900, 'L', 'volantino')",
        uuid.uuid4(),
        uid,
        fid,
    )
    sql(
        "INSERT INTO receipt_line (id, user_id, receipt_id, testo_grezzo, quantita, prezzo, fonte)"
        " VALUES ($1, $2, $3, 'BANANE', 1.234, 2.58, 'scontrino')",
        uuid.uuid4(),
        uid,
        rid,
    )
    riga = sql("SELECT quantita, sconto, stato FROM receipt_line")[0]
    assert str(riga["quantita"]) == "1.234"
    assert riga["sconto"] == 0
    assert riga["stato"] == "auto"
    assert sql("SELECT condizione FROM offer")[0]["condizione"] == "nessuna"


def test_condizione_o_unita_dell_offerta_fuori_dall_insieme_respinte(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    fid = uuid.uuid4()
    sql(_FLYER, fid, uid, "abc")
    ins = (
        "INSERT INTO offer (id, user_id, flyer_id, testo_grezzo, condizione, unita, fonte)"
        " VALUES ($1, $2, $3, 'x', $4, $5, 'volantino')"
    )
    with pytest.raises(asyncpg.CheckViolationError):
        sql(ins, uuid.uuid4(), uid, fid, "sconto_famiglia", "kg")
    with pytest.raises(asyncpg.CheckViolationError):
        sql(ins, uuid.uuid4(), uid, fid, "nessuna", "etto")


def test_cancellando_volantino_e_scontrino_spariscono_le_righe_ma_non_il_prodotto(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    pid = _nuovo_prodotto(sql, uid)
    fid, rid = uuid.uuid4(), uuid.uuid4()
    sql(_FLYER, fid, uid, "abc")
    sql(_RECEIPT, rid, uid, "lidl")
    sql(
        "INSERT INTO offer (id, user_id, flyer_id, testo_grezzo, product_id, fonte)"
        " VALUES ($1, $2, $3, 'x', $4, 'volantino')",
        uuid.uuid4(),
        uid,
        fid,
        pid,
    )
    sql(
        "INSERT INTO receipt_line (id, user_id, receipt_id, testo_grezzo, quantita, prezzo, fonte,"
        " product_id) VALUES ($1, $2, $3, 'x', 1, 1, 'scontrino', $4)",
        uuid.uuid4(),
        uid,
        rid,
        pid,
    )
    sql("DELETE FROM flyer WHERE id = $1", fid)
    sql("DELETE FROM receipt WHERE id = $1", rid)
    assert sql("SELECT 1 FROM offer") == []
    assert sql("SELECT 1 FROM receipt_line") == []
    assert sql("SELECT 1 FROM product WHERE id = $1", pid)


_INVENTARIO = (
    "INSERT INTO inventory_item (id, user_id, group_id, livello, livello_confidenza)"
    " VALUES ($1, $2, $3, $4, $5)"
)


def test_secondo_inventory_item_per_lo_stesso_gruppo_e_utente_respinto(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    gid = _nuovo_gruppo(sql, uid)
    sql(_INVENTARIO, uuid.uuid4(), uid, gid, 0, "bassa")
    with pytest.raises(asyncpg.UniqueViolationError):
        sql(_INVENTARIO, uuid.uuid4(), uid, gid, 1, "media")
    altro = _nuovo_utente(sql)
    sql(_INVENTARIO, uuid.uuid4(), altro, _nuovo_gruppo(sql, altro), 0, "bassa")


def test_livello_o_livello_confidenza_fuori_dall_insieme_respinti(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    gid = _nuovo_gruppo(sql, uid)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(_INVENTARIO, uuid.uuid4(), uid, gid, 3, "bassa")
    with pytest.raises(asyncpg.CheckViolationError):
        sql(_INVENTARIO, uuid.uuid4(), uid, gid, -1, "bassa")
    with pytest.raises(asyncpg.CheckViolationError):
        sql(_INVENTARIO, uuid.uuid4(), uid, gid, 2, "altissima")


def test_inventory_item_con_default_e_quantita_esatte(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    gid = _nuovo_gruppo(sql, uid)
    sql(
        "INSERT INTO inventory_item (id, user_id, group_id, quantita_ultimo_acquisto, livello,"
        " livello_confidenza) VALUES ($1, $2, $3, 6.000, 1, 'media')",
        uuid.uuid4(),
        uid,
        gid,
    )
    riga = sql("SELECT * FROM inventory_item")[0]
    assert riga["tasso_consumo"] is None
    assert riga["probabilmente_finito"] is False
    assert str(riga["quantita_ultimo_acquisto"]) == "6.000"


def test_job_nuovo_e_pending_senza_tentativi_e_stato_fuori_dall_insieme_respinto(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    sql(
        "INSERT INTO job (id, user_id, tipo, payload) VALUES ($1, $2, 'ricalcolo_notturno',"
        " '{\"x\": 1}'::jsonb)",
        uuid.uuid4(),
        uid,
    )
    riga = sql("SELECT * FROM job")[0]
    assert (riga["stato"], riga["tentativi"], riga["lease_scade_il"]) == ("pending", 0, None)
    with pytest.raises(asyncpg.CheckViolationError):
        sql(
            "INSERT INTO job (id, user_id, tipo, stato) VALUES ($1, $2, 'x', 'cancelled')",
            uuid.uuid4(),
            uid,
        )


def test_cancellando_l_utente_spariscono_magazzino_e_job(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    sql(_INVENTARIO, uuid.uuid4(), uid, _nuovo_gruppo(sql, uid), 0, "bassa")
    sql("INSERT INTO job (id, user_id, tipo) VALUES ($1, $2, 'x')", uuid.uuid4(), uid)
    sql("DELETE FROM app_user WHERE id = $1", uid)
    assert sql("SELECT 1 FROM inventory_item") == []
    assert sql("SELECT 1 FROM job") == []


def _altro_prodotto_e_gruppo(sql: Sql) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    a, b = _nuovo_utente(sql), _nuovo_utente(sql)
    return a, b, _nuovo_gruppo(sql, b), _nuovo_prodotto(sql, b)


def test_riga_di_un_utente_non_puo_puntare_al_catalogo_di_un_altro(
    migrated: Config, sql: Sql
) -> None:
    a, b, gruppo_b, prodotto_b = _altro_prodotto_e_gruppo(sql)
    gruppo_a, fid, rid = _nuovo_gruppo(sql, a), uuid.uuid4(), uuid.uuid4()
    sql(_FLYER, fid, b, "abc")
    sql(_RECEIPT, rid, b, "lidl")
    violazioni = [
        (
            "INSERT INTO product (id, user_id, nome, group_id, unita_di_vendita, fonte)"
            " VALUES ($1, $2, 'x', $3, 'pezzo', 'umano')",
            (uuid.uuid4(), a, gruppo_b),
        ),
        (_ALIAS, (uuid.uuid4(), a, prodotto_b, "auto")),
        (
            "INSERT INTO group_alternative (id, user_id, group_a, group_b, fonte)"
            " VALUES ($1, $2, $3, $4, 'umano')",
            (uuid.uuid4(), a, gruppo_a, gruppo_b),
        ),
        (
            "INSERT INTO group_alternative (id, user_id, group_a, group_b, fonte)"
            " VALUES ($1, $2, $3, $4, 'umano')",
            (uuid.uuid4(), a, gruppo_b, gruppo_a),
        ),
        (
            "INSERT INTO offer (id, user_id, flyer_id, testo_grezzo, fonte)"
            " VALUES ($1, $2, $3, 'x', 'volantino')",
            (uuid.uuid4(), a, fid),
        ),
        (
            "INSERT INTO offer (id, user_id, flyer_id, testo_grezzo, product_id, fonte)"
            " VALUES ($1, $2, $3, 'x', $4, 'volantino')",
            (uuid.uuid4(), a, _flyer_di(sql, a), prodotto_b),
        ),
        (
            "INSERT INTO receipt_line (id, user_id, receipt_id, testo_grezzo, quantita, prezzo,"
            " fonte) VALUES ($1, $2, $3, 'x', 1, 1, 'scontrino')",
            (uuid.uuid4(), a, rid),
        ),
        (
            "INSERT INTO receipt_line (id, user_id, receipt_id, testo_grezzo, quantita, prezzo,"
            " fonte, product_id) VALUES ($1, $2, $3, 'x', 1, 1, 'scontrino', $4)",
            (uuid.uuid4(), a, _scontrino_di(sql, a), prodotto_b),
        ),
        (_INVENTARIO, (uuid.uuid4(), a, gruppo_b, 1, "alta")),
    ]
    for query, args in violazioni:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            sql(query, *args)


def _flyer_di(sql: Sql, uid: uuid.UUID) -> uuid.UUID:
    fid = uuid.uuid4()
    sql(_FLYER, fid, uid, uuid.uuid4().hex)
    return fid


def _scontrino_di(sql: Sql, uid: uuid.UUID) -> uuid.UUID:
    rid = uuid.uuid4()
    sql(_RECEIPT, rid, uid, "lidl")
    return rid


def test_cancellando_gruppo_o_prodotto_si_annulla_solo_il_riferimento(
    migrated: Config, sql: Sql
) -> None:
    uid = _nuovo_utente(sql)
    gid = _nuovo_gruppo(sql, uid)
    pid = _nuovo_prodotto(sql, uid, gid)
    fid, rid = _flyer_di(sql, uid), _scontrino_di(sql, uid)
    sql(
        "INSERT INTO offer (id, user_id, flyer_id, testo_grezzo, product_id, fonte)"
        " VALUES ($1, $2, $3, 'x', $4, 'volantino')",
        uuid.uuid4(),
        uid,
        fid,
        pid,
    )
    sql(
        "INSERT INTO receipt_line (id, user_id, receipt_id, testo_grezzo, quantita, prezzo, fonte,"
        " product_id) VALUES ($1, $2, $3, 'x', 1, 1, 'scontrino', $4)",
        uuid.uuid4(),
        uid,
        rid,
        pid,
    )
    sql("DELETE FROM product_group WHERE id = $1", gid)
    prodotto = sql("SELECT user_id, group_id FROM product WHERE id = $1", pid)[0]
    assert prodotto["user_id"] == uid
    assert prodotto["group_id"] is None
    sql("DELETE FROM product WHERE id = $1", pid)
    for tabella in ("offer", "receipt_line"):
        riga = sql(f"SELECT user_id, product_id FROM {tabella}")[0]
        assert riga["user_id"] == uid
        assert riga["product_id"] is None


def test_quantita_della_riga_non_positiva_respinta(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    rid = _scontrino_di(sql, uid)
    ins = (
        "INSERT INTO receipt_line (id, user_id, receipt_id, testo_grezzo, quantita, prezzo, fonte)"
        " VALUES ($1, $2, $3, 'x', $4::numeric, 1, 'scontrino')"
    )
    for quantita in ("0", "-1"):
        with pytest.raises(asyncpg.CheckViolationError):
            sql(ins, uuid.uuid4(), uid, rid, quantita)
    sql(ins, uuid.uuid4(), uid, rid, "0.250")


def test_dimensione_base_non_positiva_respinta_ma_puo_mancare(migrated: Config, sql: Sql) -> None:
    uid = _nuovo_utente(sql)
    ins = (
        "INSERT INTO product (id, user_id, nome, unita_di_vendita, dimensione_base, fonte)"
        " VALUES ($1, $2, 'x', 'pezzo', $3::numeric, 'umano')"
    )
    for dimensione in ("0", "-1"):
        with pytest.raises(asyncpg.CheckViolationError):
            sql(ins, uuid.uuid4(), uid, dimensione)
    sql(ins, uuid.uuid4(), uid, None)
    sql(ins, uuid.uuid4(), uid, "6")
