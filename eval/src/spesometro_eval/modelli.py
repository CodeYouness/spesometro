"""Formato dei file del golden set e delle predizioni salvate."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from spesometro_core import PaginaVolantino, Scontrino


class _Formato(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Testata(_Formato):
    """`testata.json`: versione e data del golden set, citate da ogni report."""

    versione: str = Field(min_length=1)
    data: date


class _DatiPredizione(_Formato):
    """Campi comuni a ogni predizione: chi l'ha prodotta, con quale prompt, a che costo."""

    modello: str = Field(min_length=1)
    versione_prompt: str = Field(min_length=1)
    costo_usd: Decimal | None = None
    tempo_s: float | None = None


class AnnotazioneScontrino(_Formato):
    immagine: str = Field(min_length=1)
    """Percorso relativo dentro `data/`."""
    contenuto: Scontrino


class PredizioneScontrino(AnnotazioneScontrino, _DatiPredizione):
    """Un'annotazione più modello, versione del prompt, costo e tempo."""


class AnnotazionePagina(_Formato):
    """Una pagina di volantino annotata per intero (ADR 0015)."""

    immagine: str = Field(min_length=1)
    """Percorso relativo dentro `data/`."""
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    """Impronta della pagina, confrontata con `manifest.json` quando i dati sono presenti."""
    contenuto: PaginaVolantino


class PredizionePagina(AnnotazionePagina, _DatiPredizione):
    """Un'annotazione di pagina più modello, versione del prompt, costo e tempo."""
