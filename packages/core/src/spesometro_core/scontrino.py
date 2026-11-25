"""Schema di estrazione dello scontrino (SPEC §2.1, §4.1; ADR 0007).

Ciò che il modello di visione deve restituire per uno scontrino, con i range-check che rifiutano
le estrazioni assurde. Nessun campo di pagamento, carta o fidelity: non vengono mai chiesti.
Gli importi sono `Decimal`, mai `float`.
"""

from datetime import date, time
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from spesometro_core.enumerazioni import Catena

PRIMO_ANNO = date(2020, 1, 1)

Prezzo = Annotated[Decimal, Field(ge=Decimal(-100), le=Decimal(500))]
Totale = Annotated[Decimal, Field(ge=Decimal(0), le=Decimal(2000))]
Quantita = Annotated[Decimal, Field(gt=Decimal(0), le=Decimal(100))]
ImportoSconto = Annotated[Decimal, Field(ge=Decimal(0), le=Decimal(2000))]


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RigaScontrino(_Schema):
    testo_grezzo: str
    quantita: Quantita
    """Pezzi o kg."""
    prezzo: Prezzo
    """Totale di riga prima dello sconto; negativo per resi e vuoti a rendere."""
    sconto: Decimal = Decimal(0)
    """Sconto legato a questa riga, 0 se assente."""

    @model_validator(mode="after")
    def _sconto_entro_il_prezzo(self) -> Self:
        if self.sconto != 0 and not Decimal(0) <= self.sconto <= self.prezzo:
            raise ValueError("lo sconto deve stare tra 0 e il prezzo della riga")
        return self


class ScontoScontrino(_Schema):
    """Sconto non legato a una riga (buono, sconto sul totale)."""

    descrizione: str
    importo: ImportoSconto


class Scontrino(_Schema):
    catena: Catena
    data: date | None = None
    ora: time | None = None
    totale: Totale
    righe: list[RigaScontrino]
    sconti_scontrino: list[ScontoScontrino] = Field(default_factory=list)

    @field_validator("data")
    @classmethod
    def _data_tra_2020_e_oggi(cls, valore: date | None) -> date | None:
        if valore is not None and not PRIMO_ANNO <= valore <= date.today():
            raise ValueError("la data deve stare tra il 2020 e oggi")
        return valore


def discrepanza_somma_totale(scontrino: Scontrino) -> Decimal:
    """Σ(prezzo − sconto) − Σ sconti di scontrino − totale.

    Zero se le righe tornano con il totale; positivo se le righe sommano più del totale.
    Il retry che la usa è del ticket di estrazione degli scontrini.
    """
    righe = sum((r.prezzo - r.sconto for r in scontrino.righe), Decimal(0))
    sconti = sum((s.importo for s in scontrino.sconti_scontrino), Decimal(0))
    return righe - sconti - scontrino.totale


def json_schema_scontrino() -> dict[str, Any]:
    """JSON Schema per lo structured output (`json_schema`).

    I limiti che i provider non accettano (range numerici, sconto ≤ prezzo, data ≤ oggi) restano
    validati da Pydantic sulla risposta.
    """
    return Scontrino.model_json_schema(mode="validation")
