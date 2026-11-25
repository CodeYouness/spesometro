"""Loader del golden set e delle predizioni: ogni errore nomina il file e il campo."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ValidationError

from spesometro_eval.modelli import (
    AnnotazionePagina,
    AnnotazioneScontrino,
    PredizionePagina,
    PredizioneScontrino,
    Testata,
)

NOME_TESTATA = "testata.json"
NOME_MANIFEST = "manifest.json"
CARTELLA_SCONTRINI = "scontrini"
CARTELLA_VOLANTINI = "volantini"


class ErroreGolden(Exception):
    """Un file del golden set o delle predizioni non è valido."""


@dataclass
class GoldenSet:
    testata: Testata
    scontrini: list[tuple[Path, AnnotazioneScontrino]]
    pagine: list[tuple[Path, AnnotazionePagina]] = field(default_factory=list)
    avvisi: list[str] = field(default_factory=list)


@dataclass
class Predizioni:
    scontrini: list[tuple[Path, PredizioneScontrino]] = field(default_factory=list)
    pagine: list[tuple[Path, PredizionePagina]] = field(default_factory=list)


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
    """Carica testata e annotazioni; immagini mancanti e sha256 diversi sono avvisi."""
    testata_file = golden / NOME_TESTATA
    if not testata_file.is_file():
        raise ErroreGolden(f"{testata_file}: testata mancante (servono versione e data)")
    testata = _leggi(testata_file, Testata)

    scontrini = [
        (f, _leggi(f, AnnotazioneScontrino))
        for f in sorted((golden / CARTELLA_SCONTRINI).glob("*.json"))
    ]
    pagine = [
        (f, _leggi(f, AnnotazionePagina))
        for f in sorted((golden / CARTELLA_VOLANTINI).glob("*.json"))
    ]
    avvisi = [
        f"{f}: immagine mancante in {data / a.immagine}"
        for f, a in [*scontrini, *pagine]
        if not (data / a.immagine).is_file()
    ]
    avvisi += [avviso for f, a in pagine for avviso in _controlla_sha256(f, a, data)]
    return GoldenSet(testata, scontrini, pagine, avvisi)


def _trova_manifest(data: Path, immagine: str) -> Path | None:
    """Il `manifest.json` più vicino alla pagina, risalendo fino a `data/`."""
    cartella = (data / immagine).parent
    while True:
        candidato = cartella / NOME_MANIFEST
        if candidato.is_file():
            return candidato
        if cartella == data or cartella == cartella.parent:
            return None
        cartella = cartella.parent


def _sha256_da_manifest(manifest: Path, immagine: str, data: Path) -> str | None:
    """Impronta della pagina secondo il manifest (voci con `cartella` e `pagine[].file`)."""
    voci = json.loads(manifest.read_text())
    base = PurePosixPath(*manifest.parent.relative_to(data).parts)
    for voce in voci:
        for pagina in voce.get("pagine", []):
            if str(base / voce["cartella"] / pagina["file"]) == immagine:
                return pagina["sha256"]
    return None


def _controlla_sha256(file: Path, a: AnnotazionePagina, data: Path) -> list[str]:
    manifest = _trova_manifest(data, a.immagine)
    if manifest is None:
        return [f"{file}: {NOME_MANIFEST} assente, sha256 non verificato"]
    try:
        atteso = _sha256_da_manifest(manifest, a.immagine, data)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return [f"{file}: {manifest} non leggibile, sha256 non verificato"]
    if atteso is None:
        return [f"{file}: {a.immagine} non compare in {manifest}, sha256 non verificato"]
    if atteso != a.sha256:
        return [f"{file}: sha256 diverso da {manifest} (annotazione {a.sha256}, manifest {atteso})"]
    return []


def carica_predizioni(cartella: Path) -> Predizioni:
    """Una predizione di pagina ha `contenuto.offerte`, una di scontrino `contenuto.righe`."""
    if not cartella.is_dir():
        raise ErroreGolden(f"{cartella}: cartella delle predizioni mancante")
    risultato = Predizioni()
    for f in sorted(cartella.glob("*.json")):
        if _e_pagina(f):
            risultato.pagine.append((f, _leggi(f, PredizionePagina)))
        else:
            risultato.scontrini.append((f, _leggi(f, PredizioneScontrino)))
    return risultato


def _e_pagina(file: Path) -> bool:
    try:
        contenuto = json.loads(file.read_text()).get("contenuto")
    except (OSError, ValueError, AttributeError):
        return False  # l'errore vero lo darà `_leggi`, nominando il file
    return isinstance(contenuto, dict) and "offerte" in contenuto


def sha256_pagina(data: Path, immagine: str) -> str:
    """Impronta di una pagina: dal file se c'è, altrimenti dal `manifest.json`."""
    file = data / immagine
    if file.is_file():
        return hashlib.sha256(file.read_bytes()).hexdigest()
    manifest = _trova_manifest(data, immagine)
    if manifest is not None:
        try:
            atteso = _sha256_da_manifest(manifest, immagine, data)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            atteso = None
        if atteso is not None:
            return atteso
    raise ErroreGolden(
        f"{file}: immagine assente e pagina non nel manifest, impossibile ricavare lo sha256"
    )


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


def scheletro_pagina(immagine: str, sha256: str) -> str:
    """Annotazione vuota di una pagina di volantino, da completare a mano."""
    scheletro = {"immagine": immagine, "sha256": sha256, "contenuto": {"offerte": []}}
    return json.dumps(scheletro, indent=2, ensure_ascii=False) + "\n"
