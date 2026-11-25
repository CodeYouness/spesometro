"""Comandi: `scheletro`, `valida`, `report`. Nessuna chiamata a modelli, nessuna rete."""

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from spesometro_eval.caricamento import (
    CARTELLA_SCONTRINI,
    ErroreGolden,
    carica_golden,
    carica_predizioni,
    scheletro_annotazione,
)
from spesometro_eval.report import costruisci_report

RADICE = Path(__file__).resolve().parents[3]
GOLDEN = RADICE / "eval" / "golden"
DATA = RADICE / "data"
REPORTS = RADICE / "eval" / "reports"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spesometro-eval", description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)

    scheletro = sub.add_parser("scheletro", help="crea l'annotazione vuota di uno scontrino")
    scheletro.add_argument("immagine", help="percorso relativo dentro data/, es. scontrini/a.jpg")
    scheletro.add_argument("--golden", type=Path, default=GOLDEN)

    valida = sub.add_parser("valida", help="controlla testata e annotazioni del golden set")
    valida.add_argument("--golden", type=Path, default=GOLDEN)
    valida.add_argument("--data", type=Path, default=DATA)

    report = sub.add_parser("report", help="scrive il report markdown da golden set e predizioni")
    report.add_argument("--golden", type=Path, default=GOLDEN)
    report.add_argument("--data", type=Path, default=DATA)
    report.add_argument("--predizioni", type=Path, required=True)
    report.add_argument("--out", type=Path, default=REPORTS)
    return parser


def _scheletro(args: argparse.Namespace) -> int:
    destinazione = args.golden / CARTELLA_SCONTRINI / f"{Path(args.immagine).stem}.json"
    if destinazione.exists():
        raise ErroreGolden(f"{destinazione}: esiste già, non la sovrascrivo")
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    destinazione.write_text(scheletro_annotazione(args.immagine))
    print(destinazione)
    return 0


def _valida(args: argparse.Namespace) -> int:
    golden = carica_golden(args.golden, args.data)
    for avviso in golden.avvisi:
        print(f"AVVISO {avviso}", file=sys.stderr)
    print(f"OK: {len(golden.scontrini)} scontrini, golden set versione {golden.testata.versione}")
    return 0


def _report(args: argparse.Namespace) -> int:
    golden = carica_golden(args.golden, args.data)
    predizioni = carica_predizioni(args.predizioni)
    annotate = {a.immagine for _, a in golden.scontrini}
    avvisi = golden.avvisi + [
        f"{f}: predizione senza annotazione per {p.immagine}"
        for f, p in predizioni
        if p.immagine not in annotate
    ]
    for avviso in avvisi:
        print(f"AVVISO {avviso}", file=sys.stderr)
    args.out.mkdir(parents=True, exist_ok=True)
    destinazione = args.out / f"report-golden-{golden.testata.versione}-{date.today()}.md"
    destinazione.write_text(costruisci_report(golden, predizioni, avvisi))
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
