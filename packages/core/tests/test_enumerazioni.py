from spesometro_core import Attributo, Catena, TipoEsclusione


def test_catene_ammesse() -> None:
    assert {c.value for c in Catena} == {"lidl", "eurospin", "coop", "altra"}


def test_attributi_ammessi() -> None:
    assert {a.value for a in Attributo} == {
        "maiale",
        "carne",
        "pesce",
        "alcol",
        "glutine",
        "lattosio",
        "frutta_a_guscio",
    }


def test_tipi_di_esclusione() -> None:
    assert {t.value for t in TipoEsclusione} == {"allergia", "dieta"}
