"""Scorer dell'estrazione: funzioni pure, annotazioni e predizioni in, metriche fuori.

Scontrini: le righe si allineano per sequenza (sottosequenza comune più lunga) sul testo
normalizzato; una riga saltata è una riga mancante e non sfalsa le successive.
"""

import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from spesometro_core import Scontrino

_PUNTEGGIATURA = re.compile(r"[^\w\s]|_")


def normalizza(testo: str) -> str:
    """Maiuscole, spazi e punteggiatura non contano nell'allineamento."""
    return " ".join(_PUNTEGGIATURA.sub("", testo.casefold()).split())


def allinea[T](
    annotati: Sequence[T], predetti: Sequence[T], chiave: Callable[[T], str]
) -> list[tuple[int, int]]:
    """Coppie (indice annotato, indice predetto) della sottosequenza comune più lunga."""
    a = [chiave(x) for x in annotati]
    p = [chiave(x) for x in predetti]
    lung = [[0] * (len(p) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(p) - 1, -1, -1):
            lung[i][j] = (
                lung[i + 1][j + 1] + 1 if a[i] == p[j] else max(lung[i + 1][j], lung[i][j + 1])
            )
    coppie: list[tuple[int, int]] = []
    i = j = 0
    while i < len(a) and j < len(p):
        if a[i] == p[j]:
            coppie.append((i, j))
            i += 1
            j += 1
        elif lung[i + 1][j] >= lung[i][j + 1]:
            i += 1
        else:
            j += 1
    return coppie


@dataclass
class MetricheScontrini:
    n_scontrini: int = 0
    corretti: Counter[str] = field(default_factory=Counter)
    totali: Counter[str] = field(default_factory=Counter)
    cifre_sbagliate: int = 0
    cifre_totali: int = 0

    @property
    def accuratezza(self) -> dict[str, float]:
        """Quota di valori identici all'annotazione, per campo."""
        return {c: self.corretti[c] / n for c, n in self.totali.items() if n}

    @property
    def cifre_errate(self) -> float:
        """Quota dei campi numerici con valore diverso, righe mancanti e inventate comprese."""
        return self.cifre_sbagliate / self.cifre_totali if self.cifre_totali else 0.0


_CAMPI_RIGA = ("testo_grezzo", "quantita", "prezzo", "sconto")
_NUMERICI_RIGA = ("quantita", "prezzo", "sconto")


def valuta_scontrini(coppie: Sequence[tuple[Scontrino, Scontrino]]) -> MetricheScontrini:
    """Coppie (annotato, predetto) → accuratezza per campo e tasso di cifre errate."""
    m = MetricheScontrini()
    for annotato, predetto in coppie:
        m.n_scontrini += 1
        _testata(m, annotato, predetto)
        _righe(m, annotato, predetto)
        _sconti(m, annotato, predetto)
    return m


def _conta(m: MetricheScontrini, campo: str, giusto: bool, *, numerico: bool = False) -> None:
    m.totali[campo] += 1
    m.corretti[campo] += giusto
    if numerico:
        m.cifre_totali += 1
        m.cifre_sbagliate += not giusto


def _testata(m: MetricheScontrini, annotato: Scontrino, predetto: Scontrino) -> None:
    _conta(m, "catena", annotato.catena == predetto.catena)
    _conta(m, "data", annotato.data == predetto.data)
    _conta(m, "ora", annotato.ora == predetto.ora)
    _conta(m, "totale", annotato.totale == predetto.totale, numerico=True)


def _righe(m: MetricheScontrini, annotato: Scontrino, predetto: Scontrino) -> None:
    coppie = allinea(annotato.righe, predetto.righe, lambda r: normalizza(r.testo_grezzo))
    abbinate = dict(coppie)
    for i, riga in enumerate(annotato.righe):
        trovata = predetto.righe[abbinate[i]] if i in abbinate else None
        for campo in _CAMPI_RIGA:
            giusto = trovata is not None and getattr(riga, campo) == getattr(trovata, campo)
            _conta(m, campo, giusto, numerico=campo in _NUMERICI_RIGA)
    inventate = len(predetto.righe) - len(coppie)
    m.cifre_totali += inventate * len(_NUMERICI_RIGA)
    m.cifre_sbagliate += inventate * len(_NUMERICI_RIGA)


def _sconti(m: MetricheScontrini, annotato: Scontrino, predetto: Scontrino) -> None:
    coppie = allinea(
        annotato.sconti_scontrino, predetto.sconti_scontrino, lambda s: normalizza(s.descrizione)
    )
    abbinate = dict(coppie)
    for i, sconto in enumerate(annotato.sconti_scontrino):
        trovato = predetto.sconti_scontrino[abbinate[i]] if i in abbinate else None
        giusto = trovato is not None and sconto.importo == trovato.importo
        _conta(m, "sconti_scontrino.importo", giusto, numerico=True)
    inventati = len(predetto.sconti_scontrino) - len(coppie)
    m.cifre_totali += inventati
    m.cifre_sbagliate += inventati
