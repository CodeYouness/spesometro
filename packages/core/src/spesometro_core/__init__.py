"""Dominio di Spesometro: regole, schemi, provider, minimizzazione.

Questo pacchetto non dipende da web o DB (SPEC §7).
"""

from spesometro_core.enumerazioni import (
    Attributo,
    Catena,
    Fonte,
    StatoProvenienza,
    TipoDurata,
    TipoEsclusione,
    UnitaBase,
    UnitaDiVendita,
)

__all__ = [
    "Attributo",
    "Catena",
    "Fonte",
    "StatoProvenienza",
    "TipoDurata",
    "TipoEsclusione",
    "UnitaBase",
    "UnitaDiVendita",
]
