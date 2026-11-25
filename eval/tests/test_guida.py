"""La guida "come annotare" cita gli esempi del repo: devono restare uguali ai file."""

import json
import re
from pathlib import Path

from spesometro_eval.cli import main

EVAL = Path(__file__).parents[1]
GUIDA = EVAL / "COME_ANNOTARE.md"
BLOCCHI = re.compile(r"```json (?P<file>\S+)\n(?P<corpo>.*?)\n```", re.DOTALL)


def esempi_citati() -> dict[str, str]:
    return {m["file"]: m["corpo"] for m in BLOCCHI.finditer(GUIDA.read_text())}


def test_la_guida_cita_i_due_esempi() -> None:
    assert set(esempi_citati()) == {"esempi/scontrino.json", "esempi/pagina_volantino.json"}


def test_gli_esempi_nella_guida_coincidono_con_i_file() -> None:
    for percorso, corpo in esempi_citati().items():
        assert json.loads(corpo) == json.loads((EVAL / percorso).read_text()), percorso


def test_gli_esempi_nella_guida_sono_accettati_dal_loader(tmp_path: Path) -> None:
    golden = tmp_path / "golden"
    (golden / "scontrini").mkdir(parents=True)
    (golden / "volantini").mkdir()
    (golden / "testata.json").write_text('{"versione": "esempio", "data": "2026-11-25"}')
    citati = esempi_citati()
    (golden / "scontrini" / "e.json").write_text(citati["esempi/scontrino.json"])
    (golden / "volantini" / "e.json").write_text(citati["esempi/pagina_volantino.json"])

    assert main(["valida", "--golden", str(golden), "--data", str(tmp_path / "data")]) == 0


def test_la_guida_e_raggiungibile_dal_readme_di_eval() -> None:
    assert "COME_ANNOTARE.md" in (EVAL / "README.md").read_text()
