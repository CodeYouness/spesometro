"""Dominio di Spesometro: regole, schemi, provider, minimizzazione.

Questo pacchetto non dipende da web o DB (SPEC §7).
"""

from spesometro_core.enumerazioni import (
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
from spesometro_core.scontrino import (
    RigaScontrino,
    ScontoScontrino,
    Scontrino,
    discrepanza_somma_totale,
    json_schema_scontrino,
)

__all__ = [
    "RigaScontrino",
    "Scontrino",
    "ScontoScontrino",
    "discrepanza_somma_totale",
    "json_schema_scontrino",
    "Attributo",
    "Catena",
    "CondizioneOfferta",
    "Fonte",
    "LivelloConfidenza",
    "StatoJob",
    "StatoProvenienza",
    "TipoDurata",
    "TipoEsclusione",
    "TipoVolantino",
    "UnitaBase",
    "UnitaDiVendita",
]
