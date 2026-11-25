"""Schema di estrazione della pagina di volantino (SPEC §2.1, §3.2).

Una pagina è una lista di offerte. I campi facoltativi restano vuoti se non sono stampati e non
si calcolano mai. La validità mancante si eredita dal `Flyer` al salvataggio, non qui.
Gli importi sono `Decimal`, mai `float`.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spesometro_core.enumerazioni import CondizioneOfferta, UnitaBase

PrezzoOfferta = Annotated[Decimal, Field(ge=Decimal("0.01"), le=Decimal(500))]
QuantitaOfferta = Annotated[int, Field(ge=1, le=50)]


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OffertaVolantino(_Schema):
    testo_grezzo: str
    prezzo_confezione: PrezzoOfferta
    condizione: CondizioneOfferta
    marca: str | None = None
    confezione_quantita: Annotated[Decimal, Field(gt=Decimal(0))] | None = None
    """Dimensione della confezione: quantità, nell'unità di `confezione_unita`."""
    confezione_unita: UnitaBase | None = None
    prezzo_unitario: PrezzoOfferta | None = None
    unita: UnitaBase | None = None
    """Unità a cui si riferisce `prezzo_unitario`."""
    prezzo_barrato: PrezzoOfferta | None = None
    sconto_dichiarato: Annotated[Decimal, Field(ge=Decimal(0), le=Decimal(100))] | None = None
    """Percentuale stampata sul volantino (35 per «-35%»)."""
    validita_da: date | None = None
    validita_a: date | None = None
    quantita_minima: QuantitaOfferta | None = None
    limite_pezzi: QuantitaOfferta | None = None

    @model_validator(mode="after")
    def _validita_ordinata(self) -> Self:
        if self.validita_da and self.validita_a and self.validita_a < self.validita_da:
            raise ValueError("validita_a non può precedere validita_da")
        return self


class PaginaVolantino(_Schema):
    offerte: list[OffertaVolantino]


def json_schema_pagina_volantino() -> dict[str, Any]:
    """JSON Schema per lo structured output (`json_schema`).

    I limiti che i provider non accettano restano validati da Pydantic sulla risposta.
    """
    return PaginaVolantino.model_json_schema(mode="validation")
