from typing import Any

import pytest
from spesometro_core import PaginaVolantino
from spesometro_eval.scorer import valuta_volantini


def offerta(testo: str, prezzo: str, **extra: Any) -> dict[str, Any]:
    return {"testo_grezzo": testo, "prezzo_confezione": prezzo, "condizione": "nessuna"} | extra


def pagina(*offerte: dict[str, Any]) -> PaginaVolantino:
    return PaginaVolantino.model_validate({"offerte": list(offerte)})


P1 = "raw/volantini/lidl/a/page_001.webp"
P2 = "raw/volantini/lidl/a/page_002.webp"
P3 = "raw/volantini/coop/b/page_001.webp"


def test_prezzo_giusto_validita_sbagliata_conta_per_il_gate_non_per_il_severo() -> None:
    annotata = pagina(
        offerta("Latte UHT 1L", "1.29", validita_a="2026-11-07"),
        offerta("Pane", "0.99"),
    )
    predetta = pagina(
        offerta("Latte UHT 1L", "1.29", validita_a="2026-11-08"),
        offerta("Pane", "0.99"),
    )

    m = valuta_volantini([(P1, annotata, predetta)]).totale

    assert (m.estratte, m.annotate) == (2, 2)
    assert (m.corrette_gate, m.corrette_severo) == (2, 1)
    assert m.precision_gate == 1.0
    assert m.recall_gate == 1.0
    assert m.precision_severo == 0.5
    assert m.recall_severo == 0.5


def test_prezzo_diverso_di_un_centesimo_non_accoppia() -> None:
    annotata = pagina(offerta("Latte UHT 1L", "1.29"))
    predetta = pagina(offerta("Latte UHT 1L", "1.30"))

    m = valuta_volantini([(P1, annotata, predetta)]).totale

    assert m.corrette_gate == 0
    assert m.precision_gate == 0.0
    assert m.recall_gate == 0.0


def test_offerta_duplicata_dal_modello_e_un_errore() -> None:
    annotata = pagina(offerta("Latte UHT 1L", "1.29"))
    predetta = pagina(offerta("Latte UHT 1L", "1.29"), offerta("Latte UHT 1 L", "1.29"))

    m = valuta_volantini([(P1, annotata, predetta)]).totale

    assert (m.estratte, m.annotate, m.corrette_gate) == (2, 1, 1)
    assert m.precision_gate == 0.5
    assert m.recall_gate == 1.0


def test_accoppiamento_uno_a_uno_massimizza_le_coppie() -> None:
    # La prima estratta somiglia a entrambe le annotate (1,0 e 0,77); la seconda solo alla prima
    # annotata (0,77, contro 0,42). Un accoppiamento avido per somiglianza ne farebbe una sola.
    annotata = pagina(offerta("Yogurt greco bianco", "1.00"), offerta("Yogurt greco", "1.00"))
    predetta = pagina(offerta("Yogurt greco bianco", "1.00"), offerta("Greco bianco", "1.00"))

    m = valuta_volantini([(P1, annotata, predetta)], soglia=0.6).totale

    assert m.corrette_gate == 2


def test_effetto_della_soglia_di_somiglianza() -> None:
    # Somiglianza dei nomi normalizzati: 0,88.
    annotata = pagina(offerta("Pasta Barilla spaghetti 500g", "0.89"))
    predetta = pagina(offerta("Barilla spaghetti 500g", "0.89"))

    larga = valuta_volantini([(P1, annotata, predetta)], soglia=0.6).totale
    stretta = valuta_volantini([(P1, annotata, predetta)], soglia=0.9).totale

    assert larga.corrette_gate == 1
    assert stretta.corrette_gate == 0


def test_normalizzazione_del_nome_maiuscole_spazi_punteggiatura() -> None:
    annotata = pagina(offerta("LATTE  uht, 1L", "1.29"))
    predetta = pagina(offerta("latte uht 1l", "1.29"))

    m = valuta_volantini([(P1, annotata, predetta)], soglia=1.0).totale

    assert m.corrette_gate == 1


def test_pagina_senza_estratte_ha_precision_nulla_e_recall_zero() -> None:
    m = valuta_volantini([(P1, pagina(offerta("Pane", "0.99")), pagina())]).totale

    assert m.precision_gate is None
    assert m.recall_gate == 0.0


def test_aggregazione_per_pagina_per_volantino_e_totale() -> None:
    # P1: 2 annotate, 2 estratte, 2 corrette. P2: 2 annotate, 1 estratta giusta e 1 inventata,
    # 1 corretta. P3 (altro volantino): 1 annotata, 1 estratta giusta.
    risultato = valuta_volantini(
        [
            (
                P1,
                pagina(offerta("Latte", "1.00"), offerta("Pane", "2.00")),
                pagina(offerta("Latte", "1.00"), offerta("Pane", "2.00")),
            ),
            (
                P2,
                pagina(offerta("Burro", "3.00"), offerta("Uova", "4.00")),
                pagina(offerta("Burro", "3.00"), offerta("Olio", "9.00")),
            ),
            (P3, pagina(offerta("Riso", "1.50")), pagina(offerta("Riso", "1.50"))),
        ]
    )

    per_pagina = {nome: m for nome, m in risultato.per_pagina}
    assert per_pagina[P2].precision_gate == 0.5
    assert per_pagina[P2].recall_gate == 0.5

    per_volantino = {nome: m for nome, m in risultato.per_volantino}
    assert set(per_volantino) == {"raw/volantini/lidl/a", "raw/volantini/coop/b"}
    lidl = per_volantino["raw/volantini/lidl/a"]
    assert (lidl.estratte, lidl.annotate, lidl.corrette_gate) == (4, 4, 3)
    assert lidl.precision_gate == pytest.approx(0.75)
    assert lidl.recall_gate == pytest.approx(0.75)
    assert per_volantino["raw/volantini/coop/b"].precision_gate == 1.0

    totale = risultato.totale
    assert (totale.estratte, totale.annotate, totale.corrette_gate) == (5, 5, 4)
    assert totale.precision_gate == pytest.approx(0.8)
    assert totale.recall_gate == pytest.approx(0.8)
