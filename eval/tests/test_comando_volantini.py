import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from spesometro_core import PaginaVolantino
from spesometro_eval.cli import main

CARTELLA = "raw/volantini/lidl/2026-11-01_2026-12-31_abc"
IMMAGINE = f"{CARTELLA}/page_001.webp"
BYTES = b"pagina sintetica"
SHA = hashlib.sha256(BYTES).hexdigest()

LATTE = {"testo_grezzo": "Latte UHT 1L", "prezzo_confezione": "1.29", "condizione": "nessuna"}
PANE = {"testo_grezzo": "Pane", "prezzo_confezione": "0.99", "condizione": "nessuna"}


def scrivi(percorso: Path, dati: Any) -> Path:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(dati))
    return percorso


class Cartelle:
    def __init__(self, base: Path) -> None:
        self.golden = base / "golden"
        self.data = base / "data"
        self.predizioni = base / "predizioni"
        self.reports = base / "reports"

    def testata(self) -> None:
        scrivi(self.golden / "testata.json", {"versione": "1", "data": "2026-11-25"})

    def annotazione(self, offerte: list[dict[str, Any]], nome: str = "p1", **extra: Any) -> Path:
        dati = {"immagine": IMMAGINE, "sha256": SHA, "contenuto": {"offerte": offerte}} | extra
        return scrivi(self.golden / "volantini" / f"{nome}.json", dati)

    def immagine(self) -> None:
        percorso = self.data / IMMAGINE
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_bytes(BYTES)

    def manifest(self, sha: str = SHA) -> None:
        voce = {
            "catena": "lidl",
            "cartella": "lidl/2026-11-01_2026-12-31_abc",
            "pagine": [{"n": 1, "file": "page_001.webp", "sha256": sha}],
        }
        scrivi(self.data / "raw" / "volantini" / "manifest.json", [voce])

    def predizione(self, offerte: list[dict[str, Any]], nome: str = "p1", **extra: Any) -> Path:
        dati = {
            "immagine": IMMAGINE,
            "sha256": SHA,
            "contenuto": {"offerte": offerte},
            "modello": "modello-prova",
            "versione_prompt": "p1",
        } | extra
        return scrivi(self.predizioni / f"{nome}.json", dati)

    def argomenti(self, comando: str, *extra: str) -> list[str]:
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
            *extra,
        ]

    def report(self) -> str:
        (file,) = self.reports.glob("*.md")
        return file.read_text()


@pytest.fixture
def cartelle(tmp_path: Path) -> Cartelle:
    c = Cartelle(tmp_path)
    c.testata()
    return c


def test_sha256_diverso_dal_manifest_e_un_avviso(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.annotazione([LATTE])
    cartelle.immagine()
    cartelle.manifest(sha="f" * 64)
    cartelle.predizione([LATTE])

    assert main(cartelle.argomenti("report")) == 0

    avviso = capsys.readouterr().err
    assert "sha256" in avviso
    assert "p1.json" in avviso
    assert cartelle.report()


def test_sha256_uguale_al_manifest_nessun_avviso(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.annotazione([LATTE])
    cartelle.immagine()
    cartelle.manifest()
    cartelle.predizione([LATTE])

    assert main(cartelle.argomenti("report")) == 0

    assert capsys.readouterr().err == ""


def test_manifest_assente_e_un_avviso(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.annotazione([LATTE])
    cartelle.immagine()
    cartelle.predizione([LATTE])

    assert main(cartelle.argomenti("report")) == 0

    assert "manifest.json" in capsys.readouterr().err


def test_annotazione_di_pagina_non_valida_nomina_file_e_campo(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.annotazione([LATTE], nome="buona")
    cartelle.annotazione([LATTE | {"prezzo_confezione": "0"}], nome="rotta")

    assert main(cartelle.argomenti("report")) != 0

    err = capsys.readouterr().err
    assert "rotta.json" in err
    assert "prezzo_confezione" in err
    assert "buona.json" not in err


def test_sha256_malformato_rifiutato(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    cartelle.annotazione([LATTE], sha256="abc")

    assert main(["valida", "--golden", str(cartelle.golden), "--data", str(cartelle.data)]) != 0

    assert "sha256" in capsys.readouterr().err


def test_report_con_le_due_colonne_la_soglia_e_i_criteri(cartelle: Cartelle) -> None:
    # Una pagina: Latte con validità sbagliata (gate sì, severo no), Pane giusto, Burro inventato.
    cartelle.annotazione([LATTE | {"validita_a": "2026-11-07"}, PANE])
    cartelle.immagine()
    cartelle.manifest()
    cartelle.predizione(
        [
            LATTE | {"validita_a": "2026-11-08"},
            PANE,
            {**PANE, "testo_grezzo": "Burro", "prezzo_confezione": "2.49"},
        ],
        costo_usd="0.01",
        tempo_s=3.0,
    )

    assert main(cartelle.argomenti("report", "--soglia", "0.7")) == 0

    testo = cartelle.report()
    assert "ADR 0015" in testo
    assert "0,7" in testo  # soglia usata
    assert "Precision (gate)" in testo
    assert "Precision (severo)" in testo
    assert "Recall (gate)" in testo
    assert "Recall (severo)" in testo
    assert "| Totale | 3 | 2 | 66,7% | 100,0% | 33,3% | 50,0% |" in testo
    assert f"| {IMMAGINE} |" in testo
    assert f"| {CARTELLA} |" in testo
    assert "0.01" in testo


def test_report_mostra_l_esito_del_gate(cartelle: Cartelle) -> None:
    cartelle.annotazione([LATTE, PANE])
    cartelle.predizione([LATTE, PANE])

    assert main(cartelle.argomenti("report")) == 0

    assert "Gate di S1 (precision gate ≥ 70%): superato" in cartelle.report()


def test_soglia_default_e_0_6(cartelle: Cartelle) -> None:
    cartelle.annotazione([LATTE])
    cartelle.predizione([LATTE])

    assert main(cartelle.argomenti("report")) == 0

    assert "soglia di somiglianza 0,6" in cartelle.report()


def test_scheletro_di_pagina_accettato_dal_loader(cartelle: Cartelle) -> None:
    cartelle.immagine()
    cartelle.manifest()

    codice = main(
        ["scheletro", IMMAGINE, "--tipo", "pagina", "--golden", str(cartelle.golden)]
        + ["--data", str(cartelle.data)]
    )

    assert codice == 0
    creato = cartelle.golden / "volantini" / "lidl_2026-11-01_2026-12-31_abc_page_001.json"
    dati = json.loads(creato.read_text())
    assert dati["immagine"] == IMMAGINE
    assert dati["sha256"] == SHA
    assert main(["valida", "--golden", str(cartelle.golden), "--data", str(cartelle.data)]) == 0


def test_scheletri_della_stessa_pagina_di_due_volantini_non_collidono(cartelle: Cartelle) -> None:
    altra = "raw/volantini/coop/2026-09-24_2026-10-21_coop-1/page_001.webp"
    for immagine in (IMMAGINE, altra):
        percorso = cartelle.data / immagine
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_bytes(BYTES)

        codice = main(
            ["scheletro", immagine, "--tipo", "pagina", "--golden", str(cartelle.golden)]
            + ["--data", str(cartelle.data)]
        )

        assert codice == 0
    creati = sorted(p.name for p in (cartelle.golden / "volantini").glob("*.json"))
    assert creati == [
        "coop_2026-09-24_2026-10-21_coop-1_page_001.json",
        "lidl_2026-11-01_2026-12-31_abc_page_001.json",
    ]


@pytest.mark.parametrize("forma", ["relativa", "assoluta"])
def test_scheletro_accetta_il_percorso_con_la_cartella_data(
    cartelle: Cartelle, monkeypatch: pytest.MonkeyPatch, forma: str
) -> None:
    cartelle.immagine()
    monkeypatch.chdir(cartelle.data.parent)
    immagine = f"data/{IMMAGINE}" if forma == "relativa" else str(cartelle.data / IMMAGINE)

    codice = main(
        ["scheletro", immagine, "--tipo", "pagina", "--golden", str(cartelle.golden)]
        + ["--data", str(cartelle.data)]
    )

    assert codice == 0
    (creato,) = (cartelle.golden / "volantini").glob("*.json")
    assert json.loads(creato.read_text())["immagine"] == IMMAGINE


def test_scheletro_di_pagina_senza_immagine_ne_manifest_fallisce(
    cartelle: Cartelle, capsys: pytest.CaptureFixture[str]
) -> None:
    codice = main(
        ["scheletro", IMMAGINE, "--tipo", "pagina", "--golden", str(cartelle.golden)]
        + ["--data", str(cartelle.data)]
    )

    assert codice != 0
    assert "sha256" in capsys.readouterr().err


def test_esempio_sintetico_di_pagina_valido(tmp_path: Path) -> None:
    esempio = Path(__file__).parents[1] / "esempi" / "pagina_volantino.json"
    base = tmp_path / "golden"
    scrivi(base / "testata.json", {"versione": "esempio", "data": "2026-11-25"})
    (base / "volantini").mkdir()
    (base / "volantini" / "esempio.json").write_text(esempio.read_text())

    assert main(["valida", "--golden", str(base), "--data", str(tmp_path / "data")]) == 0
    PaginaVolantino.model_validate(json.loads(esempio.read_text())["contenuto"])


def test_pagina_annotata_senza_predizione_conta_come_vuota_e_il_report_lo_dice(
    cartelle: Cartelle,
) -> None:
    seconda = f"{CARTELLA}/page_002.webp"
    cartelle.annotazione([LATTE])
    cartelle.annotazione([LATTE], nome="p2", immagine=seconda)
    cartelle.predizione([LATTE])

    assert main(cartelle.argomenti("report")) == 0

    testo = cartelle.report()
    assert "Pagine valutate: 1 su 2." in testo
    assert "senza predizione contano come estrazione vuota" in testo
    assert "| Totale | 1 | 2 | 100,0% | 50,0% | 100,0% | 50,0% |" in testo
    assert f"| {seconda} | 0 | 1 | n/d | 0,0% | n/d | 0,0% |" in testo


def test_report_spiega_che_il_severo_confronta_anche_il_testo_grezzo(cartelle: Cartelle) -> None:
    cartelle.annotazione([LATTE])
    cartelle.predizione([LATTE])

    assert main(cartelle.argomenti("report")) == 0

    testo = cartelle.report()
    assert "`testo_grezzo` carattere per carattere" in testo
