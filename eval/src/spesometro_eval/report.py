"""Report markdown: versione e data del golden set, metriche, costo e tempo se presenti."""

from collections import defaultdict
from decimal import Decimal

from spesometro_eval.caricamento import GoldenSet, Predizioni
from spesometro_eval.modelli import (
    AnnotazionePagina,
    AnnotazioneScontrino,
    PredizionePagina,
    PredizioneScontrino,
)
from spesometro_eval.scorer import (
    SOGLIA_SOMIGLIANZA,
    ConteggiOfferte,
    MetricheScontrini,
    valuta_scontrini,
    valuta_volantini,
)

SOGLIA_GATE_PRECISION = 0.7
"""Gate di S1 (SPEC §3.2): precision delle offerte, criterio del gate, almeno 70%."""


def percentuale(valore: float | None) -> str:
    if valore is None:
        return "n/d"
    return f"{valore * 100:.1f}%".replace(".", ",")


def _numero(valore: float) -> str:
    return f"{valore:g}".replace(".", ",")


def costruisci_report(
    golden: GoldenSet,
    predizioni: Predizioni,
    avvisi: list[str],
    soglia: float = SOGLIA_SOMIGLIANZA,
) -> str:
    scontrini = {a.immagine: a for _, a in golden.scontrini}
    pagine = {a.immagine: a for _, a in golden.pagine}
    gruppi_s: dict[tuple[str, str], list[PredizioneScontrino]] = defaultdict(list)
    for _, p in predizioni.scontrini:
        if p.immagine in scontrini:
            gruppi_s[(p.modello, p.versione_prompt)].append(p)
    gruppi_p: dict[tuple[str, str], list[PredizionePagina]] = defaultdict(list)
    for _, q in predizioni.pagine:
        if q.immagine in pagine:
            gruppi_p[(q.modello, q.versione_prompt)].append(q)

    righe = [
        "# Report eval: scontrini e volantini",
        "",
        f"Golden set: versione {golden.testata.versione}, data {golden.testata.data.isoformat()}.",
        f"Scontrini annotati: {len(scontrini)}. Pagine di volantino annotate: {len(pagine)}.",
    ]
    for chiave in sorted(gruppi_s.keys() | gruppi_p.keys()):
        modello, prompt = chiave
        righe += ["", f"## {modello} (prompt {prompt})"]
        if chiave in gruppi_s:
            righe += _sezione_scontrini(gruppi_s[chiave], scontrini)
        if chiave in gruppi_p:
            righe += _sezione_volantini(gruppi_p[chiave], pagine, soglia)
    if not gruppi_s and not gruppi_p:
        righe += ["", "Nessuna predizione corrispondente a un'annotazione."]
    if avvisi:
        righe += ["", "## Avvisi", "", *[f"- {a}" for a in avvisi]]
    return "\n".join(righe) + "\n"


def _costo_e_tempo(gruppo: list[PredizioneScontrino] | list[PredizionePagina]) -> list[str]:
    righe = []
    costi = [p.costo_usd for p in gruppo if p.costo_usd is not None]
    if costi:
        righe.append(f"| Costo totale (USD) | {sum(costi, Decimal(0))} |")
    tempi = [p.tempo_s for p in gruppo if p.tempo_s is not None]
    if tempi:
        righe.append(f"| Tempo medio per elemento (s) | {sum(tempi) / len(tempi):.1f} |")
    return righe


def _sezione_scontrini(
    gruppo: list[PredizioneScontrino], annotati: dict[str, AnnotazioneScontrino]
) -> list[str]:
    metriche: MetricheScontrini = valuta_scontrini(
        [(annotati[p.immagine].contenuto, p.contenuto) for p in gruppo]
    )
    righe = [
        "",
        "### Scontrini",
        "",
        f"Scontrini valutati: {metriche.n_scontrini} su {len(annotati)}.",
        "",
        "| Metrica | Valore |",
        "|---|---|",
    ]
    righe += [f"| Accuratezza `{c}` | {percentuale(v)} |" for c, v in metriche.accuratezza.items()]
    righe.append(f"| Tasso di cifre errate | {percentuale(metriche.cifre_errate)} |")
    return righe + _costo_e_tempo(gruppo)


def _riga_offerte(nome: str, c: ConteggiOfferte) -> str:
    return (
        f"| {nome} | {c.estratte} | {c.annotate} | {percentuale(c.precision_gate)} "
        f"| {percentuale(c.recall_gate)} | {percentuale(c.precision_severo)} "
        f"| {percentuale(c.recall_severo)} |"
    )


def _sezione_volantini(
    gruppo: list[PredizionePagina], annotate: dict[str, AnnotazionePagina], soglia: float
) -> list[str]:
    m = valuta_volantini(
        [(p.immagine, annotate[p.immagine].contenuto, p.contenuto) for p in gruppo], soglia
    )
    esito = (
        "n/d"
        if m.totale.precision_gate is None
        else "superato"
        if m.totale.precision_gate >= SOGLIA_GATE_PRECISION
        else "non superato"
    )
    righe = [
        "",
        "### Offerte dei volantini",
        "",
        f"Pagine valutate: {len(gruppo)} su {len(annotate)}.",
        "",
        "Criteri (ADR 0015). **Gate**: nella stessa pagina, un'offerta estratta è corretta se si "
        "accoppia uno a uno con un'annotata per `prezzo_confezione` identico al centesimo e "
        f"nome normalizzato simile (soglia di somiglianza {_numero(soglia)}). "
        "**Severo**, solo informativo: la coppia del gate vale solo se tutti i campi coincidono.",
        "",
        f"Gate di S1 (precision gate ≥ 70%): {esito}.",
        "",
        "| Livello | Estratte | Annotate | Precision (gate) | Recall (gate) "
        "| Precision (severo) | Recall (severo) |",
        "|---|---|---|---|---|---|---|",
        _riga_offerte("Totale", m.totale),
    ]
    righe += [_riga_offerte(nome, c) for nome, c in m.per_volantino]
    righe += [_riga_offerte(nome, c) for nome, c in m.per_pagina]
    costo_e_tempo = _costo_e_tempo(gruppo)
    if costo_e_tempo:
        righe += ["", "| Metrica | Valore |", "|---|---|", *costo_e_tempo]
    return righe
