"""Forma dello schema verificata dai metadati, senza database."""

import re

from spesometro_core import (
    Attributo,
    Catena,
    CondizioneOfferta,
    Fonte,
    LivelloConfidenza,
    StatoJob,
    StatoProvenienza,
    TipoDurata,
    TipoEsclusione,
    TipoVolantino,
    UnitaBase,
    UnitaDiVendita,
)
from spesometro_db import Base
from spesometro_db.models import (
    Exclusion,
    Flyer,
    GroupAlternative,
    InventoryItem,
    Job,
    Offer,
    Product,
    ProductAlias,
    ProductGroup,
    Receipt,
    ReceiptLine,
    User,
)
from sqlalchemy import CheckConstraint, Index, Table, UniqueConstraint


def _tabelle_utente() -> list[Table]:
    return [t for t in Base.metadata.sorted_tables if t.name != User.__tablename__]


def _valori_check(tabella: Table, nome: str) -> set[str]:
    """Valori letterali citati nel CHECK `nome` (nome logico, senza prefisso)."""
    for c in tabella.constraints:
        if isinstance(c, CheckConstraint) and c.name == f"ck_{tabella.name}_{nome}":
            return set(re.findall(r"'([^']+)'", str(c.sqltext)))
    raise AssertionError(f"CHECK {nome} assente su {tabella.name}")


def test_ogni_tabella_ha_user_id_non_nullo_con_cascata_verso_user() -> None:
    tabelle = _tabelle_utente()
    assert Exclusion.__table__ in tabelle
    for tabella in tabelle:
        colonna = tabella.c.user_id
        assert not colonna.nullable, tabella.name
        (fk,) = [
            f
            for f in tabella.foreign_key_constraints
            if f.referred_table.name == User.__tablename__
        ]
        assert fk.column_keys == ["user_id"], tabella.name
        assert fk.ondelete == "CASCADE", tabella.name


def test_ogni_chiave_esterna_tra_tabelle_utente_include_user_id() -> None:
    """Una riga dell'utente A non può puntare a una riga dell'utente B (ADR 0014 punto 17)."""
    viste = 0
    for tabella in _tabelle_utente():
        for fk in tabella.foreign_key_constraints:
            if fk.referred_table.name == User.__tablename__:
                continue
            viste += 1
            assert "user_id" in fk.column_keys, fk.name
            assert {e.column.name for e in fk.elements} >= {"user_id", "id"}, fk.name
            assert any(
                {c.name for c in u.columns} == {"user_id", "id"}
                for u in fk.referred_table.constraints
                if isinstance(u, UniqueConstraint)
            ), fk.name
    assert viste == 9


def test_set_null_annulla_solo_la_colonna_del_riferimento() -> None:
    for tabella, colonna in (
        (Product.__table__, "group_id"),
        (Offer.__table__, "product_id"),
        (ReceiptLine.__table__, "product_id"),
    ):
        (fk,) = [f for f in tabella.foreign_key_constraints if colonna in f.column_keys]
        assert fk.ondelete == f"SET NULL ({colonna})", tabella.name


def test_check_coincidono_con_le_enumerazioni_di_core() -> None:
    esclusione = Exclusion.__table__
    assert _valori_check(esclusione, "attributo") == {a.value for a in Attributo}
    assert _valori_check(esclusione, "tipo") == {t.value for t in TipoEsclusione}

    utente = User.__table__
    assert _valori_check(utente, "carte_fedelta") == {c.value for c in Catena}
    assert _valori_check(utente, "catena_abituale") == {c.value for c in Catena}


def test_esclusione_unica_per_utente_e_attributo() -> None:
    unici = [
        [c.name for c in u.columns]
        for u in Exclusion.__table__.constraints
        if isinstance(u, UniqueConstraint)
    ]
    pk = [c.name for c in Exclusion.__table__.primary_key.columns]
    assert ["user_id", "attributo"] in unici or pk == ["user_id", "attributo"]


def test_preferenze_dell_utente_con_default() -> None:
    t = User.__table__
    assert str(t.c.risparmio_minimo_per_negozio.server_default.arg) == "5"
    assert str(t.c.max_negozi.server_default.arg) == "2"
    assert type(t.c.risparmio_minimo_per_negozio.type).__name__ == "Numeric"


COLONNE_PROVENIENZA = {"fonte", "fonte_id", "acquisito_il", "confidenza", "stato"}


def test_provenienza_solo_sulle_tabelle_che_la_prevedono() -> None:
    con = [Product, ProductAlias, GroupAlternative, Offer, ReceiptLine]
    senza = [User, Exclusion, ProductGroup, Flyer, Receipt]
    for modello in con:
        t = modello.__table__
        assert set(t.c.keys()) >= COLONNE_PROVENIENZA, t.name
        assert not t.c.fonte_id.foreign_keys, t.name
        assert _valori_check(t, "fonte") == {f.value for f in Fonte}
        assert _valori_check(t, "stato") == {s.value for s in StatoProvenienza}
        assert any(
            isinstance(c, CheckConstraint) and c.name == f"ck_{t.name}_confidenza"
            for c in t.constraints
        )
    for modello in senza:
        assert not COLONNE_PROVENIENZA & set(modello.__table__.c.keys()), modello.__tablename__


def test_check_del_catalogo_coincidono_con_le_enumerazioni_di_core() -> None:
    gruppo, prodotto = ProductGroup.__table__, Product.__table__
    assert _valori_check(gruppo, "unita_base") == {u.value for u in UnitaBase}
    assert _valori_check(gruppo, "tipo_durata") == {t.value for t in TipoDurata}
    assert _valori_check(prodotto, "unita_base") == {u.value for u in UnitaBase}
    assert _valori_check(prodotto, "unita_di_vendita") == {u.value for u in UnitaDiVendita}
    assert _valori_check(prodotto, "attributi") == {a.value for a in Attributo}
    assert _valori_check(ProductAlias.__table__, "catena") == {c.value for c in Catena}


def test_quantita_del_catalogo_sono_numeric() -> None:
    assert type(ProductGroup.__table__.c.formato_riferimento.type).__name__ == "Numeric"
    for nome in ("dimensione_originale_quantita", "dimensione_base"):
        assert type(Product.__table__.c[nome].type).__name__ == "Numeric", nome


def test_prodotto_puo_esistere_senza_gruppo() -> None:
    assert Product.__table__.c.group_id.nullable


def test_alias_unico_per_catena_e_stringa_tra_le_righe_non_rifiutate() -> None:
    indici = [i for i in ProductAlias.__table__.indexes if isinstance(i, Index) and i.unique]
    assert len(indici) == 1
    indice = indici[0]
    assert [c.name for c in indice.columns] == ["user_id", "catena", "testo_grezzo"]
    assert "rifiutato" in str(indice.dialect_options["postgresql"]["where"])


def test_alternativa_orientata_unica_e_mai_con_se_stessa() -> None:
    t = GroupAlternative.__table__
    unici = [[c.name for c in u.columns] for u in t.constraints if isinstance(u, UniqueConstraint)]
    assert ["user_id", "group_a", "group_b"] in unici
    assert any(
        isinstance(c, CheckConstraint) and c.name == "ck_group_alternative_gruppi_diversi"
        for c in t.constraints
    )


def test_nessuna_tabella_di_equivalenze() -> None:
    assert not [n for n in Base.metadata.tables if "equivalen" in n]


def _unici(tabella: Table) -> list[list[str]]:
    return [
        [c.name for c in u.columns] for u in tabella.constraints if isinstance(u, UniqueConstraint)
    ]


def test_check_delle_fonti_dei_prezzi_coincidono_con_le_enumerazioni_di_core() -> None:
    assert _valori_check(Flyer.__table__, "tipo") == {t.value for t in TipoVolantino}
    assert _valori_check(Flyer.__table__, "catena") == {c.value for c in Catena}
    assert _valori_check(Offer.__table__, "condizione") == {c.value for c in CondizioneOfferta}
    assert _valori_check(Offer.__table__, "unita") == {u.value for u in UnitaBase}
    assert _valori_check(Receipt.__table__, "catena") == {c.value for c in Catena}


def test_volantino_unico_per_utente_e_sha256() -> None:
    assert ["user_id", "sha256"] in _unici(Flyer.__table__)


def test_scontrino_unico_per_utente_catena_data_ora_e_totale() -> None:
    assert ["user_id", "catena", "data_ora", "totale"] in _unici(Receipt.__table__)


def test_importi_e_quantita_delle_fonti_sono_numeric_mai_float() -> None:
    attese = {
        Offer: [
            "prezzo_confezione",
            "prezzo_unitario",
            "prezzo_barrato",
            "sconto_dichiarato",
        ],
        Receipt: ["totale"],
        ReceiptLine: ["quantita", "prezzo", "sconto"],
    }
    for modello, colonne in attese.items():
        for nome in colonne:
            assert type(modello.__table__.c[nome].type).__name__ == "Numeric", nome


def test_data_e_ora_dello_scontrino_senza_fuso() -> None:
    assert Receipt.__table__.c.data_ora.type.timezone is False


def test_righe_figlie_cadono_con_la_sorgente_e_il_prodotto_resta_opzionale() -> None:
    for tabella, colonna in ((Offer.__table__, "flyer_id"), (ReceiptLine.__table__, "receipt_id")):
        (fk,) = tabella.c[colonna].foreign_keys
        assert fk.ondelete == "CASCADE"
        assert not tabella.c[colonna].nullable
    assert Offer.__table__.c.product_id.nullable
    assert ReceiptLine.__table__.c.product_id.nullable


def test_check_di_magazzino_e_coda_coincidono_con_le_enumerazioni_di_core() -> None:
    assert _valori_check(InventoryItem.__table__, "livello_confidenza") == {
        c.value for c in LivelloConfidenza
    }
    assert _valori_check(Job.__table__, "stato") == {s.value for s in StatoJob}
    check = next(
        c
        for c in InventoryItem.__table__.constraints
        if isinstance(c, CheckConstraint) and c.name == "ck_inventory_item_livello"
    )
    assert set(re.findall(r"\d+", str(check.sqltext))) == {"0", "1", "2"}


def test_magazzino_punta_al_gruppo_mai_al_prodotto_ed_e_unico_per_gruppo() -> None:
    tabella = InventoryItem.__table__
    bersagli = {fk.column.table.name for fk in tabella.foreign_keys}
    assert ProductGroup.__tablename__ in bersagli
    assert Product.__tablename__ not in bersagli
    unici = [
        [c.name for c in u.columns] for u in tabella.constraints if isinstance(u, UniqueConstraint)
    ]
    assert ["user_id", "group_id"] in unici


def test_magazzino_e_coda_senza_provenienza() -> None:
    for tabella in (InventoryItem.__table__, Job.__table__):
        assert not {"fonte", "fonte_id", "acquisito_il", "confidenza"} & set(tabella.c.keys())


def test_lease_del_job_con_fuso_e_quantita_del_magazzino_numeric() -> None:
    assert Job.__table__.c.lease_scade_il.type.timezone is True
    assert type(Job.__table__.c.payload.type).__name__ == "JSONB"
    for nome in ("quantita_ultimo_acquisto", "tasso_consumo"):
        assert type(InventoryItem.__table__.c[nome].type).__name__ == "Numeric"
    assert InventoryItem.__table__.c.tasso_consumo.nullable


def test_check_di_scrittura_su_quantita_e_dimensione() -> None:
    nomi = {c.name for c in ReceiptLine.__table__.constraints}
    assert "ck_receipt_line_quantita_positiva" in nomi
    assert "ck_product_dimensione_base_positiva" in {c.name for c in Product.__table__.constraints}
    assert Product.__table__.c.dimensione_base.nullable
