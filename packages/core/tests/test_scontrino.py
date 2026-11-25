import json
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from spesometro_core import Scontrino, discrepanza_somma_totale, json_schema_scontrino


def scontrino(**override: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "catena": "lidl",
        "totale": "3.50",
        "righe": [{"testo_grezzo": "LATTE UHT 1L", "quantita": "2", "prezzo": "3.50"}],
    }
    return base | override


def con_riga(**override: Any) -> dict[str, Any]:
    return scontrino(righe=[{"testo_grezzo": "X", "quantita": "1", "prezzo": "1"} | override])


def accetta(dati: dict[str, Any]) -> Scontrino:
    return Scontrino.model_validate(dati)


def rifiuta(dati: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Scontrino.model_validate(dati)


def test_scontrino_minimo_senza_data_ne_ora() -> None:
    s = accetta(scontrino())
    assert s.data is None
    assert s.ora is None
    assert s.righe[0].sconto == Decimal(0)
    assert s.sconti_scontrino == []


def test_data_e_ora_facoltative_se_presenti() -> None:
    s = accetta(scontrino(data="2026-11-02", ora="18:45"))
    assert s.data == date(2026, 11, 2)
    assert s.ora == time(18, 45)


@pytest.mark.parametrize("campo", ["catena", "totale", "righe"])
def test_campi_obbligatori(campo: str) -> None:
    dati = scontrino()
    del dati[campo]
    rifiuta(dati)


@pytest.mark.parametrize("campo", ["testo_grezzo", "quantita", "prezzo"])
def test_campi_obbligatori_di_riga(campo: str) -> None:
    dati = scontrino()
    del dati["righe"][0][campo]
    rifiuta(dati)


def test_catena_fuori_dall_enumerazione() -> None:
    rifiuta(scontrino(catena="esselunga"))


@pytest.mark.parametrize(
    "extra",
    ["carta", "pagamento", "metodo_pagamento", "fidelity", "numero_carta", "iban", "tessera"],
)
def test_nessun_campo_di_pagamento_carta_o_fidelity(extra: str) -> None:
    rifiuta(scontrino(**{extra: "x"}))
    assert not any(
        p in nome for nome in Scontrino.model_fields for p in ("pag", "carta", "fidelity")
    )


@pytest.mark.parametrize(
    ("prezzo", "valido"),
    [("-100", True), ("-100.01", False), ("500", True), ("500.01", False)],
)
def test_range_prezzo(prezzo: str, valido: bool) -> None:
    (accetta if valido else rifiuta)(con_riga(prezzo=prezzo, sconto="0"))


@pytest.mark.parametrize(
    ("totale", "valido"),
    [("0", True), ("-0.01", False), ("2000", True), ("2000.01", False)],
)
def test_range_totale(totale: str, valido: bool) -> None:
    (accetta if valido else rifiuta)(scontrino(totale=totale))


@pytest.mark.parametrize(
    ("quantita", "valido"),
    [("0", False), ("0.001", True), ("100", True), ("100.001", False), ("-1", False)],
)
def test_range_quantita(quantita: str, valido: bool) -> None:
    (accetta if valido else rifiuta)(con_riga(quantita=quantita))


@pytest.mark.parametrize(
    ("prezzo", "sconto", "valido"),
    [
        ("10", "0", True),
        ("10", "10", True),
        ("10", "10.01", False),
        ("10", "-0.01", False),
        ("-5", "0", True),
        ("-5", "1", False),
    ],
)
def test_range_sconto(prezzo: str, sconto: str, valido: bool) -> None:
    (accetta if valido else rifiuta)(con_riga(prezzo=prezzo, sconto=sconto))


def test_range_data() -> None:
    oggi = date.today()
    accetta(scontrino(data="2020-01-01"))
    rifiuta(scontrino(data="2019-12-31"))
    accetta(scontrino(data=oggi.isoformat()))
    rifiuta(scontrino(data=(oggi + timedelta(days=1)).isoformat()))


def test_gli_importi_letti_dal_json_sono_decimali() -> None:
    s = Scontrino.model_validate_json(
        '{"catena":"coop","totale":0.1,"righe":[{"testo_grezzo":"A","quantita":1,"prezzo":0.1}]}'
    )
    assert s.totale == Decimal("0.1")
    assert isinstance(s.righe[0].prezzo, Decimal)


def discrepanza(**override: Any) -> Decimal:
    return discrepanza_somma_totale(accetta(scontrino(**override)))


def test_discrepanza_zero_con_righe_semplici() -> None:
    assert discrepanza(
        totale="5.00",
        righe=[
            {"testo_grezzo": "A", "quantita": "1", "prezzo": "3.00"},
            {"testo_grezzo": "B", "quantita": "1", "prezzo": "2.00"},
        ],
    ) == Decimal(0)


def test_discrepanza_con_sconto_di_riga() -> None:
    # 3.00 - 0.50 + 2.00 = 4.50, totale dichiarato 5.00 -> -0.50
    assert discrepanza(
        totale="5.00",
        righe=[
            {"testo_grezzo": "A", "quantita": "1", "prezzo": "3.00", "sconto": "0.50"},
            {"testo_grezzo": "B", "quantita": "1", "prezzo": "2.00"},
        ],
    ) == Decimal("-0.50")


def test_discrepanza_con_sconto_di_scontrino() -> None:
    # 3.00 + 2.00 - 1.00 = 4.00 -> coerente con totale 4.00
    assert discrepanza(
        totale="4.00",
        righe=[
            {"testo_grezzo": "A", "quantita": "1", "prezzo": "3.00"},
            {"testo_grezzo": "B", "quantita": "1", "prezzo": "2.00"},
        ],
        sconti_scontrino=[{"descrizione": "BUONO", "importo": "1.00"}],
    ) == Decimal(0)


def test_discrepanza_con_reso() -> None:
    # 3.00 + 2.00 - 0.50 (vuoto a rendere) = 4.50, totale 4.00 -> +0.50
    assert discrepanza(
        totale="4.00",
        righe=[
            {"testo_grezzo": "A", "quantita": "1", "prezzo": "3.00"},
            {"testo_grezzo": "B", "quantita": "1", "prezzo": "2.00"},
            {"testo_grezzo": "VUOTO", "quantita": "1", "prezzo": "-0.50"},
        ],
    ) == Decimal("0.50")


def test_json_schema_valido_e_serializzabile() -> None:
    schema = json_schema_scontrino()
    json.dumps(schema)
    Draft202012Validator.check_schema(schema)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert {"catena", "totale", "righe"} <= set(schema["required"])
