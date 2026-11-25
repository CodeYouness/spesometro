"""Comandi: `scheletro`, `valida`, `report`. Nessuna chiamata a modelli, nessuna rete."""

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from spesometro_eval.caricamento import (
    CARTELLA_SCONTRINI,
    CARTELLA_VOLANTINI,
    ErroreGolden,
    carica_golden,
    carica_predizioni,
    scheletro_annotazione,
    scheletro_pagina,
    sha256_pagina,
)
from spesometro_eval.report import costruisci_report
from spesometro_eval.scorer import SOGLIA_SOMIGLIANZA

RADICE = Path(__file__).resolve().parents[3]
GOLDEN = RADICE / "eval" / "golden"
DATA = RADICE / "data"
REPORTS = RADICE / "eval" / "reports"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spesometro-eval", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    scheletro = sub.add_parser(
        "scheletro", help="crea l'annotazione vuota di uno scontrino o pagina"
    )
    scheletro.add_argument(
        "immagine", help="percorso dentro data/ (es. scontrini/a.jpg) o che inizia con data/"
    )
    scheletro.add_argument("--tipo", choices=["scontrino", "pagina"], default="scontrino")
    scheletro.add_argument("--golden", type=Path, default=GOLDEN)
    scheletro.add_argument("--data", type=Path, default=DATA, help="serve per lo sha256 di pagina")

    valida = sub.add_parser("valida", help="controlla testata e annotazioni del golden set")
    valida.add_argument("--golden", type=Path, default=GOLDEN)
    valida.add_argument("--data", type=Path, default=DATA)

    report = sub.add_parser("report", help="scrive il report markdown da golden set e predizioni")
    report.add_argument("--golden", type=Path, default=GOLDEN)
    report.add_argument("--data", type=Path, default=DATA)
    report.add_argument("--predizioni", type=Path, required=True)
    report.add_argument("--out", type=Path, default=REPORTS)
    report.add_argument(
        "--soglia",
        type=float,
        default=SOGLIA_SOMIGLIANZA,
        help="somiglianza minima del nome per accoppiare due offerte (default %(default)s)",
    )
    return parser


def _dentro_data(immagine: str, data: Path) -> str:
    """Accetta anche `data/raw/...` o un percorso assoluto: restituisce il percorso dentro data/."""
    percorso = Path(immagine)
    try:
        return (Path.cwd() / percorso).resolve().relative_to(data.resolve()).as_posix()
    except ValueError:
        return immagine


def _nome_scheletro(immagine: str, pagina: bool) -> str:
    """Le pagine hanno nomi ripetuti (`page_005.webp` in ogni volantino): catena e cartella
    del volantino entrano nel nome del file."""
    senza_estensione = Path(immagine).with_suffix("")
    parti = senza_estensione.parts[-3:] if pagina else (senza_estensione.name,)
    return "_".join(parti) + ".json"


def _scheletro(args: argparse.Namespace) -> int:
    pagina = args.tipo == "pagina"
    immagine = _dentro_data(args.immagine, args.data)
    cartella = CARTELLA_VOLANTINI if pagina else CARTELLA_SCONTRINI
    destinazione = args.golden / cartella / _nome_scheletro(immagine, pagina)
    if destinazione.exists():
        raise ErroreGolden(f"{destinazione}: esiste già, non la sovrascrivo")
    testo = (
        scheletro_pagina(immagine, sha256_pagina(args.data, immagine))
        if pagina
        else scheletro_annotazione(immagine)
    )
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    destinazione.write_text(testo)
    print(destinazione)
    return 0


def _valida(args: argparse.Namespace) -> int:
    golden = carica_golden(args.golden, args.data)
    for avviso in golden.avvisi:
        print(f"AVVISO {avviso}", file=sys.stderr)
    print(
        f"OK: {len(golden.scontrini)} scontrini, {len(golden.pagine)} pagine, "
        f"golden set versione {golden.testata.versione}"
    )
    return 0


def _report(args: argparse.Namespace) -> int:
    golden = carica_golden(args.golden, args.data)
    predizioni = carica_predizioni(args.predizioni)
    annotate = {a.immagine for _, a in [*golden.scontrini, *golden.pagine]}
    avvisi = golden.avvisi + [
        f"{f}: predizione senza annotazione per {p.immagine}"
        for f, p in [*predizioni.scontrini, *predizioni.pagine]
        if p.immagine not in annotate
    ]
    for avviso in avvisi:
        print(f"AVVISO {avviso}", file=sys.stderr)
    args.out.mkdir(parents=True, exist_ok=True)
    destinazione = args.out / f"report-golden-{golden.testata.versione}-{date.today()}.md"
    destinazione.write_text(costruisci_report(golden, predizioni, avvisi, args.soglia))
    print(destinazione)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    comandi = {"scheletro": _scheletro, "valida": _valida, "report": _report}
    try:
        return comandi[args.comando](args)
    except ErroreGolden as e:
        print(f"ERRORE {e}", file=sys.stderr)
        return 1
