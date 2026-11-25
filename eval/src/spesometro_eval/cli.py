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
    scheletro.add_argument("immagine", help="percorso relativo dentro data/, es. scontrini/a.jpg")
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


def _scheletro(args: argparse.Namespace) -> int:
    pagina = args.tipo == "pagina"
    cartella = CARTELLA_VOLANTINI if pagina else CARTELLA_SCONTRINI
    destinazione = args.golden / cartella / f"{Path(args.immagine).stem}.json"
    if destinazione.exists():
        raise ErroreGolden(f"{destinazione}: esiste già, non la sovrascrivo")
    testo = (
        scheletro_pagina(args.immagine, sha256_pagina(args.data, args.immagine))
        if pagina
        else scheletro_annotazione(args.immagine)
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
