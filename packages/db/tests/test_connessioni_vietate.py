"""ADR 0001: nel repo niente transaction pooler (6543) né host diretto Supabase."""

import re
import subprocess
from pathlib import Path

RADICE = Path(__file__).parents[3]

# Stringa di connessione con porta 6543, oppure host diretto `db.<ref>.supabase.co`.
VIETATI = [
    re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^\s'\"]*:6543\b"),
    re.compile(r"\bdb\.[a-z0-9]+\.supabase\.co\b"),
]
QUESTO_FILE = Path(__file__).resolve()


def _file_versionati() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=RADICE,
        capture_output=True,
        check=True,
    ).stdout
    return [RADICE / p for p in out.decode().split("\0") if p]


def test_nessuna_stringa_di_connessione_vietata() -> None:
    trovati = []
    for path in _file_versionati():
        if path.resolve() == QUESTO_FILE or not path.is_file():
            continue
        try:
            testo = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for regola in VIETATI:
            if regola.search(testo):
                trovati.append(f"{path.relative_to(RADICE)}: {regola.pattern}")
    assert not trovati, trovati


def test_il_controllo_riconosce_i_casi_vietati() -> None:
    assert VIETATI[0].search(
        "postgresql://u:p@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    )
    assert VIETATI[1].search("db.abcdefgh.supabase.co")
    assert not VIETATI[0].search(
        "postgresql://u:p@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
    )
