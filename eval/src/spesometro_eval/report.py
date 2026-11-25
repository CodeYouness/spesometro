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
    SOGLIA_GATE_PRECISION,
    SOGLIA_SOMIGLIANZA,
    ConteggiOfferte,
    MetricheScontrini,
    valuta_scontrini,
    valuta_volantini,
)

REGOLA_SENZA_PREDIZIONE = (
    "Le annotazioni senza predizione contano come estrazione vuota: offerte, righe e campi "
    "numerici annotati risultano mancanti, quindi pesano su recall, accuratezza e cifre errate."
)


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
    per_gruppo_scontrini: dict[tuple[str, str], list[PredizioneScontrino]] = defaultdict(list)
    for _, predizione in predizioni.scontrini:
        if predizione.immagine in scontrini:
            per_gruppo_scontrini[(predizione.modello, predizione.versione_prompt)].append(
                predizione
            )
    per_gruppo_pagine: dict[tuple[str, str], list[PredizionePagina]] = defaultdict(list)
    for _, predizione_pagina in predizioni.pagine:
        if predizione_pagina.immagine in pagine:
            per_gruppo_pagine[
                (predizione_pagina.modello, predizione_pagina.versione_prompt)
            ].append(predizione_pagina)

    righe = [
        "# Report eval: scontrini e volantini",
        "",
        f"Golden set: versione {golden.testata.versione}, data {golden.testata.data.isoformat()}.",
        f"Scontrini annotati: {len(scontrini)}. Pagine di volantino annotate: {len(pagine)}.",
    ]
    for gruppo in sorted(per_gruppo_scontrini.keys() | per_gruppo_pagine.keys()):
        modello, prompt = gruppo
        righe += ["", f"## {modello} (prompt {prompt})"]
        if gruppo in per_gruppo_scontrini:
            righe += _sezione_scontrini(per_gruppo_scontrini[gruppo], scontrini)
        if gruppo in per_gruppo_pagine:
            righe += _sezione_volantini(per_gruppo_pagine[gruppo], pagine, soglia)
    if not per_gruppo_scontrini and not per_gruppo_pagine:
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
    predetti = {p.immagine: p.contenuto for p in gruppo}
    metriche: MetricheScontrini = valuta_scontrini(
        [(a.contenuto, predetti.get(immagine)) for immagine, a in annotati.items()]
    )
    righe = [
        "",
        "### Scontrini",
        "",
        f"Scontrini valutati: {len(predetti)} su {len(annotati)}.",
        REGOLA_SENZA_PREDIZIONE,
        "",
        "Criteri: un valore conta se è identico all'annotazione. Le righe si allineano per "
        "sequenza sul testo normalizzato (maiuscole, spazi e punteggiatura non contano), ma "
        "`testo_grezzo` si confronta carattere per carattere: un refuso nel testo di una riga "
        "la fa contare come mancante più inventata.",
        "",
        "| Metrica | Valore |",
        "|---|---|",
    ]
    righe += [f"| Accuratezza `{c}` | {percentuale(v)} |" for c, v in metriche.accuratezza.items()]
    righe.append(f"| Tasso di cifre errate | {percentuale(metriche.cifre_errate)} |")
    return righe + _costo_e_tempo(gruppo)


def _riga_offerte(nome: str, conteggi: ConteggiOfferte) -> str:
    return (
        f"| {nome} | {conteggi.estratte} | {conteggi.annotate} "
        f"| {percentuale(conteggi.precision_gate)} | {percentuale(conteggi.recall_gate)} "
        f"| {percentuale(conteggi.precision_severo)} | {percentuale(conteggi.recall_severo)} |"
    )


def _sezione_volantini(
    gruppo: list[PredizionePagina], annotate: dict[str, AnnotazionePagina], soglia: float
) -> list[str]:
    predette = {p.immagine: p.contenuto for p in gruppo}
    metriche = valuta_volantini(
        [(immagine, a.contenuto, predette.get(immagine)) for immagine, a in annotate.items()],
        soglia,
    )
    esito = {None: "n/d", True: "superato", False: "non superato"}[metriche.totale.esito_gate]
    righe = [
        "",
        "### Offerte dei volantini",
        "",
        f"Pagine valutate: {len(predette)} su {len(annotate)}.",
        REGOLA_SENZA_PREDIZIONE,
        "",
        "Criteri (ADR 0015). **Gate**: nella stessa pagina, un'offerta estratta è corretta se si "
        "accoppia uno a uno con un'annotata per `prezzo_confezione` identico al centesimo e "
        f"nome normalizzato simile (soglia di somiglianza {_numero(soglia)}). "
        "**Severo**, solo informativo: un accoppiamento uno a uno massimo, calcolato a parte, "
        "sulle sole coppie del gate con tutti i campi uguali; confronta anche `testo_grezzo` "
        "carattere per carattere.",
        "",
        f"Gate di S1 (precision gate ≥ {_numero(SOGLIA_GATE_PRECISION * 100)}%): {esito}.",
        "",
        "| Livello | Estratte | Annotate | Precision (gate) | Recall (gate) "
        "| Precision (severo) | Recall (severo) |",
        "|---|---|---|---|---|---|---|",
        _riga_offerte("Totale", metriche.totale),
    ]
    righe += [_riga_offerte(nome, c) for nome, c in metriche.per_volantino]
    righe += [_riga_offerte(nome, c) for nome, c in metriche.per_pagina]
    costo_e_tempo = _costo_e_tempo(gruppo)
    if costo_e_tempo:
        righe += ["", "| Metrica | Valore |", "|---|---|", *costo_e_tempo]
    return righe
