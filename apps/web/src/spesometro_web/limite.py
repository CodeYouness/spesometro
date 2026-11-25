"""Limite dei tentativi di accesso: finestra mobile per indirizzo, in memoria del processo.

Un solo processo e un solo worker (SPEC §7): lo stato vive qui, in un'istanza creata
una volta in `main.py` e iniettata; ogni test ne crea una nuova.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta

MAX_FALLITI = 5
FINESTRA = timedelta(minutes=15)


class LimiteTentativi:
    def __init__(self) -> None:
        self._falliti: defaultdict[str, deque[datetime]] = defaultdict(deque)

    def _purga(self, indirizzo: str, adesso: datetime) -> deque[datetime]:
        istanti = self._falliti[indirizzo]
        while istanti and adesso - istanti[0] >= FINESTRA:
            istanti.popleft()
        if not istanti:
            del self._falliti[indirizzo]
        return istanti

    def bloccato(self, indirizzo: str, adesso: datetime) -> bool:
        return len(self._purga(indirizzo, adesso)) >= MAX_FALLITI

    def registra_fallito(self, indirizzo: str, adesso: datetime) -> None:
        self._purga(indirizzo, adesso)
        self._falliti[indirizzo].append(adesso)

    def azzera(self, indirizzo: str) -> None:
        self._falliti.pop(indirizzo, None)
