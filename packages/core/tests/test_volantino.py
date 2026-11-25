from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from spesometro_core import PaginaVolantino, json_schema_pagina_volantino


def offerta(**override: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "testo_grezzo": "Latte UHT 1L",
        "prezzo_confezione": "1.29",
        "condizione": "nessuna",
    }
    return base | override


def pagina(**override: Any) -> dict[str, Any]:
    return {"offerte": [offerta(**override)]}


def accetta(dati: dict[str, Any]) -> PaginaVolantino:
    return PaginaVolantino.model_validate(dati)


def rifiuta(dati: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PaginaVolantino.model_validate(dati)


def test_offerta_minima_con_facoltativi_vuoti() -> None:
    o = accetta(pagina()).offerte[0]
    assert o.prezzo_confezione == Decimal("1.29")
    for campo in (
        "marca",
        "confezione_quantita",
        "confezione_unita",
        "prezzo_unitario",
        "unita",
        "prezzo_barrato",
        "sconto_dichiarato",
        "validita_da",
        "validita_a",
        "quantita_minima",
        "limite_pezzi",
    ):
        assert getattr(o, campo) is None


def test_pagina_senza_offerte_e_valida() -> None:
    assert accetta({"offerte": []}).offerte == []


def test_offerta_completa() -> None:
    o = accetta(
        pagina(
            marca="Parmalat",
            confezione_quantita="6",
            confezione_unita="L",
            prezzo_unitario="1.29",
            unita="L",
            prezzo_barrato="1.99",
            sconto_dichiarato="35",
            validita_da="2026-11-01",
            validita_a="2026-11-07",
            quantita_minima=2,
            limite_pezzi=6,
            condizione="multi_acquisto",
        )
    ).offerte[0]
    assert o.validita_da == date(2026, 11, 1)
    assert o.confezione_quantita == Decimal(6)


@pytest.mark.parametrize("campo", ["testo_grezzo", "prezzo_confezione", "condizione"])
def test_campi_obbligatori(campo: str) -> None:
    dati = pagina()
    del dati["offerte"][0][campo]
    rifiuta(dati)


def test_condizione_fuori_dall_enumerazione() -> None:
    rifiuta(pagina(condizione="sempre"))


def test_campo_sconosciuto_rifiutato() -> None:
    rifiuta(pagina(carta="1234"))


@pytest.mark.parametrize("campo", ["prezzo_confezione", "prezzo_unitario", "prezzo_barrato"])
@pytest.mark.parametrize(
    ("valore", "ok"),
    [("0.01", True), ("500", True), ("0", False), ("0.009", False), ("500.01", False)],
)
def test_range_dei_prezzi(campo: str, valore: str, ok: bool) -> None:
    if ok:
        accetta(pagina(**{campo: valore}))
    else:
        rifiuta(pagina(**{campo: valore}))


@pytest.mark.parametrize("campo", ["quantita_minima", "limite_pezzi"])
@pytest.mark.parametrize(("valore", "ok"), [(1, True), (50, True), (0, False), (51, False)])
def test_range_quantita_minima_e_limite_pezzi(campo: str, valore: int, ok: bool) -> None:
    if ok:
        accetta(pagina(**{campo: valore}))
    else:
        rifiuta(pagina(**{campo: valore}))


def test_validita_a_non_precedente_a_validita_da() -> None:
    accetta(pagina(validita_da="2026-11-07", validita_a="2026-11-07"))
    rifiuta(pagina(validita_da="2026-11-07", validita_a="2026-11-06"))


def test_validita_da_sola_o_a_sola_accettata() -> None:
    accetta(pagina(validita_da="2026-11-07"))
    accetta(pagina(validita_a="2026-11-07"))


def test_json_schema_valido() -> None:
    schema = json_schema_pagina_volantino()
    Draft202012Validator.check_schema(schema)
    assert Draft202012Validator(schema).is_valid(pagina())
