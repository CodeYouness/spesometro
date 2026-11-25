"""Scorer dell'estrazione: funzioni pure, annotazioni e predizioni in, metriche fuori.

Volantini: dentro la pagina, accoppiamento uno a uno per `prezzo_confezione` identico al centesimo
e somiglianza del nome normalizzato sopra soglia (ADR 0015).

Scontrini: le righe si allineano per sequenza (sottosequenza comune più lunga) sul testo
normalizzato (il testo grezzo se il normalizzato è vuoto, per non allineare `***` con `---`);
una riga saltata è una riga mancante e non sfalsa le successive.

Un'annotazione senza predizione (`None`) vale come estrazione vuota: tutto ciò che è annotato
risulta mancante.
"""

import posixpath
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from spesometro_core import (
    OffertaVolantino,
    PaginaVolantino,
    RigaScontrino,
    Scontrino,
    ScontoScontrino,
)

_PUNTEGGIATURA = re.compile(r"[^\w\s]|_")


def normalizza(testo: str) -> str:
    """Maiuscole, spazi e punteggiatura non contano nell'allineamento."""
    return " ".join(_PUNTEGGIATURA.sub("", testo.casefold()).split())


def chiave_testo(testo: str) -> str:
    """Chiave di allineamento: il testo normalizzato, o il grezzo se la normalizzazione lo svuota."""
    return normalizza(testo) or testo


def allinea[T](
    annotati: Sequence[T], predetti: Sequence[T], chiave: Callable[[T], str]
) -> list[tuple[int, int]]:
    """Coppie (indice annotato, indice predetto) della sottosequenza comune più lunga."""
    chiavi_annotati = [chiave(x) for x in annotati]
    chiavi_predetti = [chiave(x) for x in predetti]
    # lunghezza_da[i][j]: lunghezza della sottosequenza comune di chiavi_annotati[i:] e [j:].
    lunghezza_da = [[0] * (len(chiavi_predetti) + 1) for _ in range(len(chiavi_annotati) + 1)]
    for i in range(len(chiavi_annotati) - 1, -1, -1):
        for j in range(len(chiavi_predetti) - 1, -1, -1):
            lunghezza_da[i][j] = (
                lunghezza_da[i + 1][j + 1] + 1
                if chiavi_annotati[i] == chiavi_predetti[j]
                else max(lunghezza_da[i + 1][j], lunghezza_da[i][j + 1])
            )
    coppie: list[tuple[int, int]] = []
    i = j = 0
    while i < len(chiavi_annotati) and j < len(chiavi_predetti):
        if chiavi_annotati[i] == chiavi_predetti[j]:
            coppie.append((i, j))
            i += 1
            j += 1
        elif lunghezza_da[i + 1][j] >= lunghezza_da[i][j + 1]:
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


def valuta_scontrini(
    coppie: Sequence[tuple[Scontrino, Scontrino | None]],
) -> MetricheScontrini:
    """Coppie (annotato, predetto) → accuratezza per campo e tasso di cifre errate.

    Un predetto `None` è un'estrazione vuota: testata sbagliata, righe e sconti tutti mancanti.
    """
    metriche = MetricheScontrini()
    for annotato, predetto in coppie:
        metriche.n_scontrini += 1
        _testata(metriche, annotato, predetto)
        _righe(metriche, annotato, predetto.righe if predetto else [])
        _sconti(metriche, annotato, predetto.sconti_scontrino if predetto else [])
    return metriche


def _registra_campo(
    metriche: MetricheScontrini, campo: str, giusto: bool, *, numerico: bool = False
) -> None:
    metriche.totali[campo] += 1
    metriche.corretti[campo] += giusto
    if numerico:
        metriche.cifre_totali += 1
        metriche.cifre_sbagliate += not giusto


def _testata(metriche: MetricheScontrini, annotato: Scontrino, predetto: Scontrino | None) -> None:
    mancante = predetto is None
    _registra_campo(metriche, "catena", not mancante and annotato.catena == predetto.catena)
    _registra_campo(metriche, "data", not mancante and annotato.data == predetto.data)
    _registra_campo(metriche, "ora", not mancante and annotato.ora == predetto.ora)
    _registra_campo(
        metriche, "totale", not mancante and annotato.totale == predetto.totale, numerico=True
    )


def _righe(
    metriche: MetricheScontrini, annotato: Scontrino, righe_predette: list[RigaScontrino]
) -> None:
    coppie = allinea(annotato.righe, righe_predette, lambda r: chiave_testo(r.testo_grezzo))
    abbinate = dict(coppie)
    for i, riga in enumerate(annotato.righe):
        trovata = righe_predette[abbinate[i]] if i in abbinate else None
        for campo in _CAMPI_RIGA:
            giusto = trovata is not None and getattr(riga, campo) == getattr(trovata, campo)
            _registra_campo(metriche, campo, giusto, numerico=campo in _NUMERICI_RIGA)
    inventate = len(righe_predette) - len(coppie)
    metriche.cifre_totali += inventate * len(_NUMERICI_RIGA)
    metriche.cifre_sbagliate += inventate * len(_NUMERICI_RIGA)


def _sconti(
    metriche: MetricheScontrini, annotato: Scontrino, sconti_predetti: list[ScontoScontrino]
) -> None:
    coppie = allinea(
        annotato.sconti_scontrino, sconti_predetti, lambda s: chiave_testo(s.descrizione)
    )
    abbinate = dict(coppie)
    for i, sconto in enumerate(annotato.sconti_scontrino):
        trovato = sconti_predetti[abbinate[i]] if i in abbinate else None
        giusto = trovato is not None and sconto.importo == trovato.importo
        _registra_campo(metriche, "sconti_scontrino.importo", giusto, numerico=True)
    inventati = len(sconti_predetti) - len(coppie)
    metriche.cifre_totali += inventati
    metriche.cifre_sbagliate += inventati


SOGLIA_SOMIGLIANZA = 0.6
"""Soglia di somiglianza del nome per accoppiare due offerte (ADR 0015)."""


def somiglianza(a: str, b: str) -> float:
    """Somiglianza dei nomi normalizzati, da 0 a 1 (rapporto di `difflib.SequenceMatcher`)."""
    return SequenceMatcher(None, chiave_testo(a), chiave_testo(b)).ratio()


SOGLIA_GATE_PRECISION = 0.7
"""Gate di S1 (SPEC §3.2): precision delle offerte, criterio del gate, almeno 70%."""


@dataclass(frozen=True)
class ConteggiOfferte:
    estratte: int = 0
    annotate: int = 0
    corrette_gate: int = 0
    """Coppie col criterio del gate: prezzo identico al centesimo e nome abbastanza simile."""
    corrette_severo: int = 0
    """Accoppiamento massimo a parte, sulle sole coppie del gate con tutti i campi uguali."""

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
    def esito_gate(self) -> bool | None:
        """`True` se la precision del gate raggiunge la soglia di S1; `None` senza estratte."""
        precision = self.precision_gate
        return None if precision is None else precision >= SOGLIA_GATE_PRECISION

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
    *,
    solo_identiche: bool = False,
) -> list[tuple[int, int]]:
    """Coppie (indice annotata, indice estratta) uno a uno, in numero massimo.

    Una coppia è ammessa se il prezzo a confezione è identico e la somiglianza del nome è almeno
    `soglia`; con `solo_identiche` anche tutti i campi devono coincidere. Per ogni estratta si preferiscono le annotate identiche, poi le più simili; un
    cammino aumentante riassegna le coppie quando serve ad accoppiarne di più.
    """
    candidate: list[list[int]] = []
    for estratta in estratte:
        ammesse = [
            (i, somiglianza(a.testo_grezzo, estratta.testo_grezzo))
            for i, a in enumerate(annotate)
            if a.prezzo_confezione == estratta.prezzo_confezione
            and (not solo_identiche or a == estratta)
        ]
        ammesse = [(i, s) for i, s in ammesse if s >= soglia]
        ammesse.sort(key=lambda x: (annotate[x[0]] != estratta, -x[1], x[0]))
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
    gate = accoppia_offerte(annotata.offerte, predetta.offerte, soglia)
    severo = accoppia_offerte(annotata.offerte, predetta.offerte, soglia, solo_identiche=True)
    return ConteggiOfferte(len(predetta.offerte), len(annotata.offerte), len(gate), len(severo))


def valuta_volantini(
    pagine: Sequence[tuple[str, PaginaVolantino, PaginaVolantino | None]],
    soglia: float = SOGLIA_SOMIGLIANZA,
) -> MetricheVolantini:
    """Terne (immagine, annotata, predetta) → conteggi per pagina, per volantino e in totale.

    Una predetta `None` è una pagina estratta vuota: tutte le offerte annotate risultano mancanti.
    """
    metriche = MetricheVolantini()
    per_volantino: dict[str, ConteggiOfferte] = {}
    for immagine, annotata, predetta in pagine:
        conteggi = _conteggi_pagina(annotata, predetta or PaginaVolantino(offerte=[]), soglia)
        metriche.per_pagina.append((immagine, conteggi))
        volantino = volantino_di(immagine)
        per_volantino[volantino] = per_volantino.get(volantino, ConteggiOfferte()) + conteggi
        metriche.totale += conteggi
    metriche.per_volantino = sorted(per_volantino.items())
    return metriche
