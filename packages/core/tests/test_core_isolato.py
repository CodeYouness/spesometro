import subprocess
import sys
import tomllib
from pathlib import Path

# Pydantic è l'unica dipendenza ammessa (SPEC, Moduli): gli schemi di dominio (scontrino, volantino)
# sono modelli Pydantic condivisi da app, worker ed eval; web e DB restano fuori da `core`.
AMMESSE = {"pydantic"}


def test_core_dipende_solo_da_pydantic() -> None:
    """`packages/core` non dipende da web o DB (SPEC §7): l'unica dipendenza è Pydantic, pinnata."""
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    dependencies = tomllib.loads(pyproject.read_text())["project"]["dependencies"]

    nomi = {d.split("==")[0] for d in dependencies}
    assert nomi == AMMESSE
    assert all("==" in d for d in dependencies)


def test_redazione_si_importa_senza_web_ne_db() -> None:
    """Importare la redazione non carica moduli web o DB."""
    codice = (
        "import sys, spesometro_core.redazione;"
        "vietati = ('nicegui','fastapi','starlette','sqlalchemy','psycopg','httpx','httpx2');"
        "print([m for m in sys.modules if m.split('.')[0] in vietati])"
    )
    risultato = subprocess.run(
        [sys.executable, "-c", codice], capture_output=True, text=True, check=True
    )
    assert risultato.stdout.strip() == "[]"
