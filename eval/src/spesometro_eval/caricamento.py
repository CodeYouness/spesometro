"""Loader del golden set e delle predizioni: ogni errore nomina il file e il campo."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ValidationError

from spesometro_eval.modelli import AnnotazioneScontrino, PredizioneScontrino, Testata

NOME_TESTATA = "testata.json"
CARTELLA_SCONTRINI = "scontrini"


class ErroreGolden(Exception):
    """Un file del golden set o delle predizioni non è valido."""


@dataclass
class GoldenSet:
    testata: Testata
    scontrini: list[tuple[Path, AnnotazioneScontrino]]
    avvisi: list[str] = field(default_factory=list)


def _leggi[M: BaseModel](percorso: Path, modello: type[M]) -> M:
    try:
        testo = percorso.read_text()
    except OSError as e:
        raise ErroreGolden(f"{percorso}: file non leggibile ({e.strerror})") from e
    try:
        return modello.model_validate_json(testo)
    except ValidationError as e:
        problemi = "; ".join(
            f"campo '{'.'.join(str(p) for p in err['loc']) or '(file)'}': {err['msg']}"
            for err in e.errors()
        )
        raise ErroreGolden(f"{percorso}: {problemi}") from e


def carica_golden(golden: Path, data: Path) -> GoldenSet:
    """Carica testata e annotazioni; immagini mancanti sono avvisi, non errori."""
    testata_file = golden / NOME_TESTATA
    if not testata_file.is_file():
        raise ErroreGolden(f"{testata_file}: testata mancante (servono versione e data)")
    testata = _leggi(testata_file, Testata)

    scontrini = [
        (f, _leggi(f, AnnotazioneScontrino))
        for f in sorted((golden / CARTELLA_SCONTRINI).glob("*.json"))
    ]
    avvisi = [
        f"{f}: immagine mancante in {data / a.immagine}"
        for f, a in scontrini
        if not (data / a.immagine).is_file()
    ]
    return GoldenSet(testata, scontrini, avvisi)


def carica_predizioni(cartella: Path) -> list[tuple[Path, PredizioneScontrino]]:
    if not cartella.is_dir():
        raise ErroreGolden(f"{cartella}: cartella delle predizioni mancante")
    return [(f, _leggi(f, PredizioneScontrino)) for f in sorted(cartella.glob("*.json"))]


def scheletro_annotazione(immagine: str) -> str:
    """Annotazione vuota di uno scontrino, da completare a mano."""
    scheletro = {
        "immagine": immagine,
        "contenuto": {
            "catena": "altra",
            "data": None,
            "ora": None,
            "totale": "0",
            "righe": [],
            "sconti_scontrino": [],
        },
    }
    return json.dumps(scheletro, indent=2, ensure_ascii=False) + "\n"
