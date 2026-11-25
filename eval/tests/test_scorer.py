from typing import Any

import pytest
from spesometro_core import Scontrino
from spesometro_eval.scorer import valuta_scontrini


def riga(testo: str, prezzo: str, quantita: str = "1", sconto: str = "0") -> dict[str, Any]:
    return {"testo_grezzo": testo, "quantita": quantita, "prezzo": prezzo, "sconto": sconto}


def scontrino(righe: list[dict[str, Any]], **testata: Any) -> Scontrino:
    base: dict[str, Any] = {"catena": "lidl", "totale": "10.00", "righe": righe}
    return Scontrino.model_validate(base | testata)


def test_righe_mancanti_e_inventate() -> None:
    annotato = scontrino(
        [riga("Latte UHT 1L", "1.50"), riga("Pane", "2.00", "2"), riga("Mele kg", "3.00", "1.5")],
        data="2026-11-02",
    )
    predetto = scontrino(
        [riga("Latte UHT 1L", "1.50"), riga("Mele kg", "3.50", "1.5"), riga("Borsa", "0.10")]
    )

    m = valuta_scontrini([(annotato, predetto)])

    # Testata: catena e totale giusti, data sbagliata (None), ora giusta (entrambe None).
    assert m.accuratezza["catena"] == 1.0
    assert m.accuratezza["data"] == 0.0
    assert m.accuratezza["ora"] == 1.0
    assert m.accuratezza["totale"] == 1.0
    # Righe annotate: 3. "Pane" manca; "Mele kg" ha il prezzo sbagliato.
    assert m.accuratezza["testo_grezzo"] == pytest.approx(2 / 3)
    assert m.accuratezza["quantita"] == pytest.approx(2 / 3)
    assert m.accuratezza["prezzo"] == pytest.approx(1 / 3)
    assert m.accuratezza["sconto"] == pytest.approx(2 / 3)
    # Campi numerici: totale 1 + 3 righe annotate x 3 + 1 riga inventata x 3 = 13.
    # Sbagliati: Pane 3 (mancante) + prezzo di Mele 1 + Borsa 3 (inventata) = 7.
    assert m.cifre_errate == pytest.approx(7 / 13)
    assert m.n_scontrini == 1


def test_una_riga_saltata_non_sfalsa_le_successive() -> None:
    annotato = scontrino(
        [riga("A", "1.00"), riga("B", "2.00"), riga("C", "3.00"), riga("D", "4.00")]
    )
    predetto = scontrino([riga("A", "1.00"), riga("C", "3.00"), riga("D", "4.00")])

    m = valuta_scontrini([(annotato, predetto)])

    assert m.accuratezza["prezzo"] == pytest.approx(3 / 4)
    # Numerici: totale 1 + 4 x 3 = 13; sbagliati: solo i 3 di B.
    assert m.cifre_errate == pytest.approx(3 / 13)


def test_allineamento_ignora_maiuscole_spazi_e_punteggiatura() -> None:
    annotato = scontrino([riga("Latte U.H.T.  1L", "1.50")])
    predetto = scontrino([riga("LATTE UHT 1L", "1.50")])

    m = valuta_scontrini([(annotato, predetto)])

    assert m.cifre_errate == 0.0
    # Il valore del testo non è identico all'annotazione, anche se la riga è allineata.
    assert m.accuratezza["testo_grezzo"] == 0.0
    assert m.accuratezza["prezzo"] == 1.0


def test_sconti_di_scontrino_contano_nelle_cifre() -> None:
    sconti = [{"descrizione": "Buono 1 euro", "importo": "1.00"}]
    annotato = scontrino([riga("A", "2.00")], sconti_scontrino=sconti)
    predetto = scontrino([riga("A", "2.00")])

    m = valuta_scontrini([(annotato, predetto)])

    # Numerici: totale 1 + riga 3 + sconto di scontrino 1 = 5; sbagliato: lo sconto mancante.
    assert m.cifre_errate == pytest.approx(1 / 5)
    assert m.accuratezza["sconti_scontrino.importo"] == 0.0


def test_aggrega_su_piu_scontrini() -> None:
    perfetto = scontrino([riga("A", "1.00")])
    sbagliato = scontrino([riga("A", "9.00")])

    m = valuta_scontrini([(perfetto, perfetto), (perfetto, sbagliato)])

    assert m.n_scontrini == 2
    assert m.accuratezza["prezzo"] == 0.5
    assert m.cifre_errate == pytest.approx(1 / 8)
