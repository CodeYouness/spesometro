"""Forma dello schema verificata dai metadati, senza database."""

import re

from spesometro_core import Attributo, Catena, TipoEsclusione
from spesometro_db import Base
from spesometro_db.models import Exclusion, User
from sqlalchemy import CheckConstraint, Table, UniqueConstraint


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
        fk = next(iter(colonna.foreign_keys))
        assert fk.column.table.name == User.__tablename__, tabella.name
        assert fk.ondelete == "CASCADE", tabella.name


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
