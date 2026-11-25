"""Formato dei file del golden set e delle predizioni salvate."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from spesometro_core import Scontrino


class _Formato(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Testata(_Formato):
    """`testata.json`: versione e data del golden set, citate da ogni report."""

    versione: str = Field(min_length=1)
    data: date


class AnnotazioneScontrino(_Formato):
    immagine: str = Field(min_length=1)
    """Percorso relativo dentro `data/`."""
    contenuto: Scontrino


class PredizioneScontrino(AnnotazioneScontrino):
    """Un'annotazione più modello, versione del prompt, costo e tempo."""

    modello: str = Field(min_length=1)
    versione_prompt: str = Field(min_length=1)
    costo_usd: Decimal | None = None
    tempo_s: float | None = None
