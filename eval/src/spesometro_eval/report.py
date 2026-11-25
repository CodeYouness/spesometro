"""Report markdown: versione e data del golden set, metriche, costo e tempo se presenti."""

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from spesometro_eval.caricamento import GoldenSet
from spesometro_eval.modelli import AnnotazioneScontrino, PredizioneScontrino
from spesometro_eval.scorer import MetricheScontrini, valuta_scontrini


def percentuale(valore: float) -> str:
    return f"{valore * 100:.1f}%".replace(".", ",")


def costruisci_report(
    golden: GoldenSet,
    predizioni: list[tuple[Path, PredizioneScontrino]],
    avvisi: list[str],
) -> str:
    annotati = {a.immagine: a for _, a in golden.scontrini}
    gruppi: dict[tuple[str, str], list[PredizioneScontrino]] = defaultdict(list)
    for _, p in predizioni:
        if p.immagine in annotati:
            gruppi[(p.modello, p.versione_prompt)].append(p)

    righe = [
        "# Report eval: scontrini",
        "",
        f"Golden set: versione {golden.testata.versione}, data {golden.testata.data.isoformat()}.",
        f"Scontrini annotati: {len(annotati)}.",
    ]
    for (modello, prompt), gruppo in sorted(gruppi.items()):
        righe += _sezione(modello, prompt, gruppo, annotati, len(annotati))
    if not gruppi:
        righe += ["", "Nessuna predizione corrispondente a un'annotazione."]
    if avvisi:
        righe += ["", "## Avvisi", "", *[f"- {a}" for a in avvisi]]
    return "\n".join(righe) + "\n"


def _sezione(
    modello: str,
    prompt: str,
    gruppo: list[PredizioneScontrino],
    annotati: dict[str, AnnotazioneScontrino],
    n_annotati: int,
) -> list[str]:
    metriche: MetricheScontrini = valuta_scontrini(
        [(annotati[p.immagine].contenuto, p.contenuto) for p in gruppo]
    )
    righe = [
        "",
        f"## {modello} (prompt {prompt})",
        "",
        f"Scontrini valutati: {metriche.n_scontrini} su {n_annotati}.",
        "",
        "| Metrica | Valore |",
        "|---|---|",
    ]
    righe += [f"| Accuratezza `{c}` | {percentuale(v)} |" for c, v in metriche.accuratezza.items()]
    righe.append(f"| Tasso di cifre errate | {percentuale(metriche.cifre_errate)} |")

    costi = [p.costo_usd for p in gruppo if p.costo_usd is not None]
    if costi:
        righe.append(f"| Costo totale (USD) | {sum(costi, Decimal(0))} |")
    tempi = [p.tempo_s for p in gruppo if p.tempo_s is not None]
    if tempi:
        righe.append(f"| Tempo medio per scontrino (s) | {sum(tempi) / len(tempi):.1f} |")
    return righe
