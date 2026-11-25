"""Loader del golden set e delle predizioni: ogni errore nomina il file e il campo."""

import hashlib
import json
from collections.abc import Sequence
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


def _leggi_tutti[M: BaseModel](
    file: Sequence[Path], modello: type[M], errori: list[str]
) -> list[tuple[Path, M]]:
    """Legge ogni file; quelli non validi finiscono in `errori`, gli altri nel risultato."""
    letti: list[tuple[Path, M]] = []
    for f in file:
        try:
            letti.append((f, _leggi(f, modello)))
        except ErroreGolden as e:
            errori.append(str(e))
    return letti


def _fallisci_se(errori: list[str]) -> None:
    if errori:
        raise ErroreGolden("\n".join(errori))


def carica_golden(golden: Path, data: Path) -> GoldenSet:
    """Carica testata e annotazioni; immagini mancanti e sha256 diversi sono avvisi.

    Se uno o più file non sono validi, l'errore li elenca tutti, ciascuno col suo campo.
    """
    errori: list[str] = []
    testata_file = golden / NOME_TESTATA
    if testata_file.is_file():
        letta = _leggi_tutti([testata_file], Testata, errori)
    else:
        letta = []
        errori.append(f"{testata_file}: testata mancante (servono versione e data)")
    scontrini = _leggi_tutti(
        sorted((golden / CARTELLA_SCONTRINI).glob("*.json")), AnnotazioneScontrino, errori
    )
    pagine = _leggi_tutti(
        sorted((golden / CARTELLA_VOLANTINI).glob("*.json")), AnnotazionePagina, errori
    )
    _fallisci_se(errori)
    testata = letta[0][1]
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
    """Impronta della pagina secondo il manifest (voci con `cartella` e `pagine[].file`).

    `None` se la pagina non compare; `ErroreGolden` se il manifest non si legge o non ha la forma
    attesa.
    """
    base = PurePosixPath(*manifest.parent.relative_to(data).parts)
    try:
        for voce in json.loads(manifest.read_text()):
            for pagina in voce.get("pagine", []):
                if str(base / voce["cartella"] / pagina["file"]) == immagine:
                    return pagina["sha256"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        raise ErroreGolden(f"{manifest}: non leggibile come manifest dei volantini") from e
    return None


def _controlla_sha256(file: Path, a: AnnotazionePagina, data: Path) -> list[str]:
    manifest = _trova_manifest(data, a.immagine)
    if manifest is None:
        return [f"{file}: {NOME_MANIFEST} assente, sha256 non verificato"]
    try:
        atteso = _sha256_da_manifest(manifest, a.immagine, data)
    except ErroreGolden:
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
    file = sorted(cartella.glob("*.json"))
    errori: list[str] = []
    risultato = Predizioni(
        scontrini=_leggi_tutti([f for f in file if not _e_pagina(f)], PredizioneScontrino, errori),
        pagine=_leggi_tutti([f for f in file if _e_pagina(f)], PredizionePagina, errori),
    )
    _fallisci_se(errori)
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
        atteso = _sha256_da_manifest(manifest, immagine, data)
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
