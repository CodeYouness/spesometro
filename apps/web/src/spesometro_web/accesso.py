"""Funzione di accesso unica: email, password e indirizzo del client -> `Esito`.

Le dipendenze arrivano dall'esterno. Il ticket 03 mette qui dentro il limite dei
tentativi (stato per indirizzo, usa `orologio`, quarto esito `TroppiTentativi`).
Il login non scrive mai nel database.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from spesometro_web.esiti import CredenzialiErrate, Esito, Riuscito
from spesometro_web.supabase_auth import Identita

type Orologio = Callable[[], datetime]  # istanti con fuso (UTC)
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
) -> Esito:
    # `''`, non `None`: gli input di NiceGUI 4.0 svuotati valgono stringa vuota.
    if not email or not password:
        return CredenzialiErrate()
    risposta = await supabase.accedi_con_password(email, password)
    if not isinstance(risposta, Identita):
        return risposta
    if not await ammesso(risposta.user_id):
        return CredenzialiErrate()
    return Riuscito(user_id=risposta.user_id, email=risposta.email)
