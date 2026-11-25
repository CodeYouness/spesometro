import copy

import pytest
from spesometro_core.redazione import PAROLE_CHIAVE_FIDELITY, redigi

# Tutti i dati sono inventati: nessuna carta o tessera reale. I codici fiscali hanno la forma
# giusta ma il giorno di nascita 99, impossibile: non possono appartenere a nessuno.


def redatta(stringa: str) -> str:
    risultato = redigi(stringa).dati
    assert isinstance(risultato, str)
    return risultato


@pytest.mark.parametrize(
    ("ingresso", "atteso"),
    [
        ("CARTA ************1234", "CARTA [PAN]"),
        ("CARTA XXXXXXXXXXXX1234", "CARTA [PAN]"),
        ("CARTA xxxxxxxxxxxx1234", "CARTA [PAN]"),
        ("CARTA ............1234", "CARTA [PAN]"),
        ("CARTA **** **** **** 1234", "CARTA [PAN]"),
        ("CARTA XXXX-XXXX-XXXX-1234", "CARTA [PAN]"),
        ("CARTA XXXX XXXX XXXX 1234 OK", "CARTA [PAN] OK"),
    ],
)
def test_pan_mascherato(ingresso: str, atteso: str) -> None:
    assert redatta(ingresso) == atteso
    assert redigi(ingresso).conteggi == {"PAN": 1}


@pytest.mark.parametrize(
    ("ingresso", "atteso"),
    [
        ("RSSMRA80A99H501U", "[CF]"),
        ("rssmra80a01h501u", "[CF]"),
        ("RSSMRA80A99H501X", "[CF]"),  # carattere di controllo sbagliato: redatto comunque
        ("RSSMRA80A99H50LU", "[CF]"),  # omocodico
        ("CF: RSSMRA80A99H501U GRAZIE", "CF: [CF] GRAZIE"),
    ],
)
def test_codice_fiscale(ingresso: str, atteso: str) -> None:
    assert redatta(ingresso) == atteso
    assert redigi(ingresso).conteggi == {"CF": 1}


@pytest.mark.parametrize(
    ("ingresso", "atteso"),
    [
        ("TESSERA 1234567890", "TESSERA [FIDELITY]"),
        ("Tessera n. 1234567890", "Tessera n. [FIDELITY]"),
        ("CARTA: 123456", "CARTA: [FIDELITY]"),
        ("SOCIO 987654321", "SOCIO [FIDELITY]"),
        ("Lidl Plus 1234567890123", "Lidl Plus [FIDELITY]"),
        ("lidl plus: 1234567890123", "lidl plus: [FIDELITY]"),
        ("CLIENTE 55443322", "CLIENTE [FIDELITY]"),
        ("Tessera: 1234 5678 9012", "Tessera: [FIDELITY]"),
        ("Tessera 1234-5678-9012 OK", "Tessera [FIDELITY] OK"),
        ("Tessera 123456 12,50", "Tessera [FIDELITY] 12,50"),
        ("Tessera N° 1234567", "Tessera N° [FIDELITY]"),
        ("carta n°1234567", "carta n°[FIDELITY]"),
        ("Carta Fedeltà 12345678", "Carta Fedeltà [FIDELITY]"),
        ("Tessera fedelta: 12345678", "Tessera fedelta: [FIDELITY]"),
        ("FIDELITY 12345678", "FIDELITY [FIDELITY]"),
        ("Fidaty 12345678", "Fidaty [FIDELITY]"),
    ],
)
def test_fidelity_dopo_parola_chiave(ingresso: str, atteso: str) -> None:
    assert redatta(ingresso) == atteso
    assert redigi(ingresso).conteggi == {"FIDELITY": 1}


@pytest.mark.parametrize("parola", PAROLE_CHIAVE_FIDELITY)
def test_ogni_parola_chiave_in_tabella_redige(parola: str) -> None:
    assert redatta(f"{parola} 1234567") == f"{parola} [FIDELITY]"
    assert redigi(f"{parola.upper()}: 1234567").conteggi == {"FIDELITY": 1}


@pytest.mark.parametrize(
    "intatta",
    [
        "TOTALE EUR 12,50",
        "1.234,56",
        "26/11/2026",
        "2026-11-26",
        "12:34:56",
        "8001234567894",  # EAN-13
        "96385074",  # EAN-8
        "PARTITA IVA 01234567890",
        "P.IVA 01234567890",
        "QTA 12345",
        "DOC. N. 0123-456789",
        "TESSERA 12345",  # meno di 6 cifre
        "TESSERA 123 45",  # meno di 6 cifre in tutto, anche a gruppi
        "ART 4006381333931 PASTA 500G",
    ],
)
def test_falsi_positivi_intatti(intatta: str) -> None:
    risultato = redigi(intatta)
    assert risultato.dati == intatta
    assert risultato.conteggi == {}


def test_piu_dati_nella_stessa_stringa() -> None:
    risultato = redigi(
        "TESSERA 1234567890 CF RSSMRA80A99H501U CARTA ****1234 e XXXX XXXX XXXX 9876"
    )
    assert risultato.dati == "TESSERA [FIDELITY] CF [CF] CARTA [PAN] e [PAN]"
    assert risultato.conteggi == {"FIDELITY": 1, "CF": 1, "PAN": 2}


def test_strutture_annidate_chiavi_e_non_stringhe_intatte() -> None:
    dati = {
        "righe": [{"descrizione": "PASTA", "prezzo": 1.5, "qta": 2, "extra": None, "ok": True}],
        "pagamento": {"nota": ["CARTA ****1234", {"x": "tessera 1234567"}]},
        "RSSMRA80A99H501U": "chiave non toccata",
    }
    risultato = redigi(dati)
    assert risultato.dati == {
        "righe": [{"descrizione": "PASTA", "prezzo": 1.5, "qta": 2, "extra": None, "ok": True}],
        "pagamento": {"nota": ["CARTA [PAN]", {"x": "tessera [FIDELITY]"}]},
        "RSSMRA80A99H501U": "chiave non toccata",
    }
    assert risultato.conteggi == {"PAN": 1, "FIDELITY": 1}


def test_ingresso_non_modificato() -> None:
    dati = {"a": ["CARTA ****1234", {"b": "RSSMRA80A99H501U"}]}
    copia = copy.deepcopy(dati)
    redigi(dati)
    assert dati == copia


def test_ripetibile() -> None:
    dati = {"a": "TESSERA 1234567890 RSSMRA80A99H501U ****1234"}
    una_volta = redigi(dati)
    due_volte = redigi(una_volta.dati)
    assert due_volte.dati == una_volta.dati
    assert due_volte.conteggi == {}


def test_conteggio_solo_numeri() -> None:
    risultato = redigi("TESSERA 1234567890 RSSMRA80A99H501U")
    assert all(isinstance(n, int) for n in risultato.conteggi.values())
    assert "1234567890" not in repr(risultato)
