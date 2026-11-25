"""Scorer dell'estrazione: funzioni pure, annotazioni e predizioni in, metriche fuori.

Volantini: dentro la pagina, accoppiamento uno a uno per `prezzo_confezione` identico al centesimo
e somiglianza del nome normalizzato sopra soglia (ADR 0015).

Scontrini: le righe si allineano per sequenza (sottosequenza comune più lunga) sul testo
normalizzato; una riga saltata è una riga mancante e non sfalsa le successive.
"""

import posixpath
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from spesometro_core import OffertaVolantino, PaginaVolantino, Scontrino

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


SOGLIA_SOMIGLIANZA = 0.6
"""Soglia di somiglianza del nome per accoppiare due offerte (ADR 0015)."""


def somiglianza(a: str, b: str) -> float:
    """Somiglianza dei nomi normalizzati, da 0 a 1 (rapporto di `difflib.SequenceMatcher`)."""
    return SequenceMatcher(None, normalizza(a), normalizza(b)).ratio()


@dataclass(frozen=True)
class ConteggiOfferte:
    estratte: int = 0
    annotate: int = 0
    corrette_gate: int = 0
    """Coppie col criterio del gate: prezzo identico al centesimo e nome abbastanza simile."""
    corrette_severo: int = 0
    """Tra le coppie del gate, quelle in cui tutti i campi coincidono (solo informativo)."""

    @staticmethod
    def _quota(corrette: int, totale: int) -> float | None:
        return corrette / totale if totale else None

    @property
    def precision_gate(self) -> float | None:
        return self._quota(self.corrette_gate, self.estratte)

    @property
    def recall_gate(self) -> float | None:
        return self._quota(self.corrette_gate, self.annotate)

    @property
    def precision_severo(self) -> float | None:
        return self._quota(self.corrette_severo, self.estratte)

    @property
    def recall_severo(self) -> float | None:
        return self._quota(self.corrette_severo, self.annotate)

    def __add__(self, altro: "ConteggiOfferte") -> "ConteggiOfferte":
        return ConteggiOfferte(
            self.estratte + altro.estratte,
            self.annotate + altro.annotate,
            self.corrette_gate + altro.corrette_gate,
            self.corrette_severo + altro.corrette_severo,
        )


@dataclass
class MetricheVolantini:
    per_pagina: list[tuple[str, ConteggiOfferte]] = field(default_factory=list)
    per_volantino: list[tuple[str, ConteggiOfferte]] = field(default_factory=list)
    totale: ConteggiOfferte = field(default_factory=ConteggiOfferte)


def volantino_di(immagine: str) -> str:
    """Il volantino è la cartella che contiene la pagina (percorso relativo dentro `data/`)."""
    return posixpath.dirname(immagine)


def accoppia_offerte(
    annotate: Sequence[OffertaVolantino],
    estratte: Sequence[OffertaVolantino],
    soglia: float = SOGLIA_SOMIGLIANZA,
) -> list[tuple[int, int]]:
    """Coppie (indice annotata, indice estratta) uno a uno, in numero massimo.

    Una coppia è ammessa se il prezzo a confezione è identico e la somiglianza del nome è almeno
    `soglia`. Per ogni estratta si preferiscono le annotate identiche, poi le più simili; un
    cammino aumentante riassegna le coppie quando serve ad accoppiarne di più.
    """
    candidate: list[list[int]] = []
    for e in estratte:
        ammesse = [
            (i, somiglianza(a.testo_grezzo, e.testo_grezzo))
            for i, a in enumerate(annotate)
            if a.prezzo_confezione == e.prezzo_confezione
        ]
        ammesse = [(i, s) for i, s in ammesse if s >= soglia]
        ammesse.sort(key=lambda x: (annotate[x[0]] != e, -x[1], x[0]))
        candidate.append([i for i, _ in ammesse])

    proprietario: dict[int, int] = {}  # indice annotata -> indice estratta

    def assegna(j: int, visitate: set[int]) -> bool:
        for i in candidate[j]:
            if i in visitate:
                continue
            visitate.add(i)
            if i not in proprietario or assegna(proprietario[i], visitate):
                proprietario[i] = j
                return True
        return False

    for j in range(len(estratte)):
        assegna(j, set())
    return sorted((i, j) for i, j in proprietario.items())


def _conteggi_pagina(
    annotata: PaginaVolantino, predetta: PaginaVolantino, soglia: float
) -> ConteggiOfferte:
    coppie = accoppia_offerte(annotata.offerte, predetta.offerte, soglia)
    identiche = sum(annotata.offerte[i] == predetta.offerte[j] for i, j in coppie)
    return ConteggiOfferte(len(predetta.offerte), len(annotata.offerte), len(coppie), identiche)


def valuta_volantini(
    pagine: Sequence[tuple[str, PaginaVolantino, PaginaVolantino]],
    soglia: float = SOGLIA_SOMIGLIANZA,
) -> MetricheVolantini:
    """Terne (immagine, annotata, predetta) → conteggi per pagina, per volantino e in totale."""
    m = MetricheVolantini()
    per_volantino: dict[str, ConteggiOfferte] = {}
    for immagine, annotata, predetta in pagine:
        c = _conteggi_pagina(annotata, predetta, soglia)
        m.per_pagina.append((immagine, c))
        chiave = volantino_di(immagine)
        per_volantino[chiave] = per_volantino.get(chiave, ConteggiOfferte()) + c
        m.totale += c
    m.per_volantino = sorted(per_volantino.items())
    return m
