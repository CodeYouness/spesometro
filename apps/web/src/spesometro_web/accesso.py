"""Funzione di accesso unica: email, password e indirizzo del client -> `Esito`.

Le dipendenze arrivano dall'esterno, compreso lo stato del limite dei tentativi.
Il login non scrive mai nel database.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError

from spesometro_web.esiti import (
    CredenzialiErrate,
    Esito,
    Riuscito,
    ServizioNonDisponibile,
    TroppiTentativi,
)
from spesometro_web.limite import LimiteTentativi
from spesometro_web.orologio import Orologio
from spesometro_web.supabase_auth import Identita

log = logging.getLogger(__name__)

type Ammesso = Callable[[uuid.UUID], Awaitable[bool]]


class ProviderAccesso(Protocol):
    async def accedi_con_password(self, email: str, password: str) -> Identita | Esito: ...


async def accedi(
    email: str,
    password: str,
    indirizzo: str,
    *,
    supabase: ProviderAccesso,
    ammesso: Ammesso,
    orologio: Orologio,
    limite: LimiteTentativi,
) -> Esito:
    if limite.bloccato(indirizzo, orologio()):
        return TroppiTentativi()
    # `''`, non `None`: gli input di NiceGUI 4.0 svuotati valgono stringa vuota.
    if not email or not password:
        return CredenzialiErrate()
    risposta = await supabase.accedi_con_password(email, password)
    if isinstance(risposta, Identita):
        try:
            presente = await ammesso(risposta.user_id)
        except (SQLAlchemyError, OSError) as errore:  # non `Exception`: `CancelledError` passa
            log.warning("Verifica di ammissione non riuscita: %s", type(errore).__name__)
            return ServizioNonDisponibile()
        if presente:
            limite.azzera(indirizzo)
            return Riuscito(user_id=risposta.user_id, email=risposta.email)
        risposta = CredenzialiErrate()  # account senza `User`: stesso esito, stesso conteggio
    if isinstance(risposta, CredenzialiErrate):
        limite.registra_fallito(indirizzo, orologio())
    return risposta
