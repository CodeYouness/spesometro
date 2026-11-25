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
from spesometro_core.volantino import (
    OffertaVolantino,
    PaginaVolantino,
    json_schema_pagina_volantino,
)

__all__ = [
    "OffertaVolantino",
    "PaginaVolantino",
    "json_schema_pagina_volantino",
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
