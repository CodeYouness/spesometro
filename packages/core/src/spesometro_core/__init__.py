"""Dominio di Spesometro: regole, schemi, provider, minimizzazione.

Questo pacchetto non dipende da web o DB (SPEC §7).
"""

from spesometro_core.enumerazioni import (
    Attributo,
    Catena,
    CondizioneOfferta,
    Fonte,
    StatoProvenienza,
    TipoDurata,
    TipoEsclusione,
    TipoVolantino,
    UnitaBase,
    UnitaDiVendita,
)

__all__ = [
    "Attributo",
    "Catena",
    "CondizioneOfferta",
    "Fonte",
    "StatoProvenienza",
    "TipoDurata",
    "TipoEsclusione",
    "TipoVolantino",
    "UnitaBase",
    "UnitaDiVendita",
]
