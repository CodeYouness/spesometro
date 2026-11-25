import json
from pathlib import Path
from typing import Any

import pytest
from spesometro_core import Scontrino, discrepanza_somma_totale
from spesometro_eval.cli import main

CONTENUTO: dict[str, Any] = {
    "catena": "lidl",
    "data": "2026-11-02",
    "totale": "3.50",
    "righe": [
        {"testo_grezzo": "LATTE UHT 1L", "quantita": "2", "prezzo": "3.50"},
    ],
}


def scrivi(percorso: Path, dati: dict[str, Any]) -> Path:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(dati))
    return percorso


class Cartelle:
    def __init__(self, base: Path) -> None:
        self.golden = base / "golden"
        self.data = base / "data"
        self.predizioni = base / "predizioni"
        self.reports = base / "reports"

    def testata(self, **override: Any) -> Path:
        dati = {"versione": "1", "data": "2026-11-25"} | override
        return scrivi(self.golden / "testata.json", dati)

    def annotazione(self, nome: str = "s1", **contenuto: Any) -> Path:
        immagine = f"scontrini/{nome}.jpg"
        dati = {"immagine": immagine, "contenuto": CONTENUTO | contenuto}
        return scrivi(self.golden / "scontrini" / f"{nome}.json", dati)

    def immagine(self, nome: str = "s1") -> None:
        percorso = self.data / "scontrini" / f"{nome}.jpg"
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_bytes(b"jpg")

    def predizione(self, nome: str = "s1", **extra: Any) -> Path:
        dati = {
            "immagine": f"scontrini/{nome}.jpg",
            "contenuto": CONTENUTO,
            "modello": "modello-prova",
            "versione_prompt": "p1",
        } | extra
        return scrivi(self.predizioni / f"{nome}.json", dati)

    def argomenti(self, comando: str) -> list[str]:
        return [
            comando,
            "--golden",
            str(self.golden),
            "--data",
            str(self.data),
            "--predizioni",
            str(self.predizioni),
            "--out",
            str(self.reports),
        ]

    def report(self) -> str:
        (file,) = self.reports.glob("*.md")
        return file.read_text()


@pytest.fixture
def cartelle(tmp_path: Path) -> Cartelle:
    return Cartelle(tmp_path)


def test_testata_mancante(cartelle: Cartelle, capsys: pytest.CaptureFixture[str]) -> None:
    cartelle.annotazione()

    assert main(cartelle.argomenti("report")) != 0

    assert "testata.json" in capsys.readouterr().err
    assert not cartelle.reports.exists()


@pytest.mark.parametrize(
    ("testata", "campo"),
    [
        ({"versione": ""}, "versione"),
        ({"data": "ieri"}, "data"),
        ({"data": None}, "data"),
    ],
)
def test_testata_non_valida(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str], testata: dict[str, Any], campo: str
) -> None:
    cartelle.testata(**testata)
    cartelle.annotazione()

    assert main(cartelle.argomenti("report")) != 0

    err = capsys.readouterr().err
    assert "testata.json" in err
    assert campo in err


def test_annotazione_non_valida_nomina_file_e_campo(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.testata()
    cartelle.annotazione("buona")
    cartelle.annotazione("rotta", totale="-5")

    assert main(cartelle.argomenti("report")) != 0

    err = capsys.readouterr().err
    assert "rotta.json" in err
    assert "totale" in err
    assert "buona.json" not in err


def test_elenca_tutti_i_file_non_validi_non_solo_il_primo(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.testata()
    cartelle.annotazione("buona")
    cartelle.annotazione("rotta1", totale="-5")
    cartelle.annotazione("rotta2", catena="inesistente")
    cartelle.predizione("buona")

    assert main(cartelle.argomenti("report")) != 0

    err = capsys.readouterr().err
    assert "rotta1.json" in err
    assert "totale" in err
    assert "rotta2.json" in err
    assert "catena" in err
    assert "buona.json" not in err


def test_elenca_tutte_le_predizioni_non_valide(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.testata()
    cartelle.annotazione()
    cartelle.predizione("a", modello=None)
    cartelle.predizione("b", versione_prompt=None)

    assert main(cartelle.argomenti("report")) != 0

    err = capsys.readouterr().err
    assert "a.json" in err
    assert "modello" in err
    assert "b.json" in err
    assert "versione_prompt" in err


def test_immagine_mancante_e_solo_un_avviso(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.testata()
    cartelle.annotazione()
    cartelle.predizione()

    assert main(cartelle.argomenti("report")) == 0

    avviso = capsys.readouterr().err
    assert "scontrini/s1.jpg" in avviso
    assert "immagine" in avviso.lower()
    assert "scontrini/s1.jpg" in cartelle.report()


def test_con_immagine_presente_nessun_avviso(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.testata()
    cartelle.annotazione()
    cartelle.immagine()
    cartelle.predizione()

    assert main(cartelle.argomenti("report")) == 0

    assert capsys.readouterr().err == ""


def test_report_con_metriche_costo_e_tempo(cartelle: Cartelle) -> None:
    cartelle.testata(versione="3", data="2026-11-20")
    cartelle.annotazione()
    cartelle.immagine()
    cartelle.predizione(costo_usd="0.0004", tempo_s=2.5)

    assert main(cartelle.argomenti("report")) == 0

    testo = cartelle.report()
    assert "versione 3" in testo
    assert "2026-11-20" in testo
    assert "modello-prova" in testo
    assert "p1" in testo
    assert "100,0%" in testo  # accuratezza di ogni campo: la predizione è identica
    assert "| Tasso di cifre errate | 0,0% |" in testo
    assert "0.0004" in testo
    assert "2.5" in testo


def test_report_senza_costo_e_tempo_non_li_mostra(cartelle: Cartelle) -> None:
    cartelle.testata()
    cartelle.annotazione()
    cartelle.immagine()
    cartelle.predizione()

    assert main(cartelle.argomenti("report")) == 0

    testo = cartelle.report().lower()
    assert "costo" not in testo
    assert "tempo" not in testo


def test_predizione_non_valida_nomina_il_file(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.testata()
    cartelle.annotazione()
    cartelle.predizione(modello=None)

    assert main(cartelle.argomenti("report")) != 0

    err = capsys.readouterr().err
    assert "s1.json" in err
    assert "modello" in err


def test_scheletro_accettato_dal_loader(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.testata()
    cartelle.immagine("nuovo")

    codice = main(["scheletro", "scontrini/nuovo.jpg", "--golden", str(cartelle.golden)])

    assert codice == 0
    creato = cartelle.golden / "scontrini" / "nuovo.json"
    assert json.loads(creato.read_text())["immagine"] == "scontrini/nuovo.jpg"
    assert main(["valida", "--golden", str(cartelle.golden), "--data", str(cartelle.data)]) == 0


def test_scheletro_non_sovrascrive(cartelle: Cartelle) -> None:
    cartelle.annotazione("nuovo")
    contenuto = (cartelle.golden / "scontrini" / "nuovo.json").read_text()

    assert main(["scheletro", "scontrini/nuovo.jpg", "--golden", str(cartelle.golden)]) != 0

    assert (cartelle.golden / "scontrini" / "nuovo.json").read_text() == contenuto


def test_esempio_sintetico_valido_e_valutabile(tmp_path: Path) -> None:
    esempi = Path(__file__).parents[1] / "esempi"
    base = tmp_path / "golden"
    scrivi(base / "testata.json", {"versione": "esempio", "data": "2026-11-25"})
    (base / "scontrini").mkdir()
    (base / "scontrini" / "esempio.json").write_text((esempi / "scontrino.json").read_text())

    assert main(["valida", "--golden", str(base), "--data", str(tmp_path / "data")]) == 0


def test_esempio_sintetico_torna_con_il_totale() -> None:
    esempio = json.loads((Path(__file__).parents[1] / "esempi" / "scontrino.json").read_text())

    assert discrepanza_somma_totale(Scontrino.model_validate(esempio["contenuto"])) == 0


def test_scontrino_annotato_senza_predizione_conta_come_vuoto_e_il_report_lo_dice(
    cartelle: Cartelle,
) -> None:
    cartelle.testata()
    cartelle.annotazione("s1")
    cartelle.annotazione("s2")
    cartelle.predizione("s1")

    assert main(cartelle.argomenti("report")) == 0

    testo = cartelle.report()
    assert "Scontrini valutati: 1 su 2." in testo
    assert "senza predizione contano come estrazione vuota" in testo
    assert "| Accuratezza `catena` | 50,0% |" in testo
    # Numerici per scontrino: totale + 3 della riga = 4; sbagliati i 4 dello scontrino mancante.
    assert "| Tasso di cifre errate | 50,0% |" in testo


def test_report_spiega_il_criterio_severo_degli_scontrini(cartelle: Cartelle) -> None:
    cartelle.testata()
    cartelle.annotazione()
    cartelle.predizione()

    assert main(cartelle.argomenti("report")) == 0

    testo = cartelle.report()
    assert "refuso" in testo
    assert "mancante più inventata" in testo
