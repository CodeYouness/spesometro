import tomllib
from pathlib import Path


def test_core_senza_dipendenze() -> None:
    """`packages/core` non dipende da web o DB (SPEC §7)."""
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    dependencies = tomllib.loads(pyproject.read_text())["project"]["dependencies"]

    assert dependencies == []
