import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

# Pydantic (schemi di dominio condivisi da app, worker ed eval) e Pillow (riduzione dell'immagine,
# ADR 0007) sono le uniche dipendenze ammesse (SPEC, Moduli); web e DB restano fuori da `core`.
AMMESSE = {"pydantic", "pillow"}
VIETATI = ("nicegui", "fastapi", "starlette", "sqlalchemy", "asyncpg", "psycopg", "httpx", "httpx2")


def test_core_dipende_solo_da_pydantic_e_pillow() -> None:
    """`packages/core` non dipende da web o DB (SPEC §7): solo Pydantic e Pillow, pinnati."""
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    dependencies = tomllib.loads(pyproject.read_text())["project"]["dependencies"]

    nomi = {d.split("==")[0] for d in dependencies}
    assert nomi == AMMESSE
    assert all("==" in d for d in dependencies)


@pytest.mark.parametrize("modulo", ["redazione", "riduzione_immagine"])
def test_importare_il_modulo_non_carica_moduli_web_o_db(modulo: str) -> None:
    codice = (
        f"import sys; import spesometro_core.{modulo}; "
        f"print([m for m in {VIETATI!r} if m in sys.modules])"
    )
    risultato = subprocess.run([sys.executable, "-c", codice], capture_output=True, text=True)

    assert risultato.returncode == 0, risultato.stderr
    assert risultato.stdout.strip() == "[]"
