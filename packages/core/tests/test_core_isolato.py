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
