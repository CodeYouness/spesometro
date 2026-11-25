"""Redazione dei dati personali dal JSON estratto da uno scontrino (ADR 0007, SPEC §3.2).

`redigi` sostituisce numero di carta mascherato, codice fiscale e codice fidelity con un segnaposto
che dice solo il tipo, e conta le sostituzioni per tipo. I valori tolti non vengono mai
restituiti né scritti nei log. Il modulo non dipende da web, DB né dalla riduzione dell'immagine.
"""

import re
from dataclasses import dataclass
from typing import NamedTuple

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None

PAN = "PAN"
CF = "CF"
FIDELITY = "FIDELITY"

_NON_ALNUM_PRIMA = r"(?<![A-Za-z0-9])"
_NON_ALNUM_DOPO = r"(?![A-Za-z0-9])"
_CIFRA_OMOCODICA = "[0-9LMNPQRSTUV]"

# Parole chiave che precedono il numero di una tessera: una riga per catena quando arrivano gli
# scontrini reali (ticket 07). Il formato delle cifre resta uguale per tutte (>= 6 cifre).
# Un nome di catena tra la parola chiave e il numero (`Carta fedeltà Esselunga 123...`) NON è
# gestito qui: i formati per catena sono del ticket 07.
PAROLE_CHIAVE_FIDELITY = (
    "tessera",
    "carta",
    "socio",
    "lidl plus",
    "cliente",
    "fidelity",
    "fidaty",
)
# Dopo la parola chiave: `fedeltà` facoltativa, poi `n`, `nr`, `num`, `numero` (con punto) o `n°`.
_PREFISSO_NUMERO = (
    r"(?:\s+fedelt[àa])?(?:\s*(?:(?:n|nr|num|numero)\.|n°|nr|num|numero|n))?\s*[:#]?\s*"
)
# Cifre in un solo blocco o a gruppi separati da un solo spazio o trattino (almeno 6 in tutto);
# un importo che segue (`12,50`) non viene inghiottito.
_NUMERO_TESSERA = r"(?=\d(?:[ -]?\d){5})\d+(?:[ -]\d+)*(?!\d)(?![.,]\d)"


class Regola(NamedTuple):
    tipo: str
    modello: re.Pattern[str]
    sostituzione: str


# Tabella unica delle regole, applicate in ordine. Il segnaposto `[TIPO]` non è riconosciuto da
# nessuna regola: la redazione è ripetibile.
REGOLE: tuple[Regola, ...] = (
    # PAN solo mascherato: almeno 4 caratteri di mascheramento, poi 4 cifre finali.
    Regola(
        PAN,
        re.compile(rf"{_NON_ALNUM_PRIMA}(?:[*X.•][ -]?){{4,}}\d{{4}}(?!\d)", re.IGNORECASE),
        "[PAN]",
    ),
    # CF di persona (16 caratteri, omocodie incluse), senza controllo del carattere finale.
    Regola(
        CF,
        re.compile(
            rf"{_NON_ALNUM_PRIMA}[A-Z]{{6}}{_CIFRA_OMOCODICA}{{2}}[ABCDEHLMPRST]"
            rf"{_CIFRA_OMOCODICA}{{2}}[A-Z]{_CIFRA_OMOCODICA}{{3}}[A-Z]{_NON_ALNUM_DOPO}",
            re.IGNORECASE,
        ),
        "[CF]",
    ),
    # Fidelity: resta la parola chiave, sparisce il numero.
    Regola(
        FIDELITY,
        re.compile(
            rf"(?P<chiave>{_NON_ALNUM_PRIMA}(?:{'|'.join(map(re.escape, PAROLE_CHIAVE_FIDELITY))})"
            rf"{_PREFISSO_NUMERO}){_NUMERO_TESSERA}",
            re.IGNORECASE,
        ),
        r"\g<chiave>[FIDELITY]",
    ),
)


@dataclass(frozen=True)
class Redatto:
    """Copia redatta e numero di sostituzioni per tipo (solo conteggi, mai i valori tolti)."""

    dati: Json
    conteggi: dict[str, int]


def redigi(dati: Json) -> Redatto:
    """Restituisce una copia di `dati` con i dati personali sostituiti; l'ingresso non cambia."""
    conteggi: dict[str, int] = {}
    return Redatto(_redigi_nodo(dati, conteggi), conteggi)


def _redigi_nodo(nodo: Json, conteggi: dict[str, int]) -> Json:
    if isinstance(nodo, str):
        return _redigi_stringa(nodo, conteggi)
    if isinstance(nodo, dict):
        return {chiave: _redigi_nodo(valore, conteggi) for chiave, valore in nodo.items()}
    if isinstance(nodo, list):
        return [_redigi_nodo(valore, conteggi) for valore in nodo]
    return nodo


def _redigi_stringa(testo: str, conteggi: dict[str, int]) -> str:
    for regola in REGOLE:
        testo, n = regola.modello.subn(regola.sostituzione, testo)
        if n:
            conteggi[regola.tipo] = conteggi.get(regola.tipo, 0) + n
    return testo
