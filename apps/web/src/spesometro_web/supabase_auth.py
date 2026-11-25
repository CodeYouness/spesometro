"""Client di Supabase Auth: accesso con password via `httpx2`, nessun SDK.

Dalla risposta si leggono solo identificativo ed email: access e refresh token
non vengono conservati né scritti nei log (nemmeno il corpo della risposta).
"""

import logging
import uuid
from dataclasses import dataclass

import httpx2

from spesometro_web.esiti import CredenzialiErrate, ServizioNonDisponibile

log = logging.getLogger(__name__)

TIMEOUT_SECONDI = 10.0
STATO_TROPPE_RICHIESTE = 429


@dataclass(frozen=True)
class Identita:
    user_id: uuid.UUID
    email: str


class ClienteSupabaseAuth:
    def __init__(self, url: str, chiave_pubblicabile: str) -> None:
        self._endpoint = f"{url.rstrip('/')}/auth/v1/token"
        self._chiave = chiave_pubblicabile

    async def accedi_con_password(
        self, email: str, password: str
    ) -> Identita | CredenzialiErrate | ServizioNonDisponibile:
        try:
            async with httpx2.AsyncClient(timeout=TIMEOUT_SECONDI) as client:
                risposta = await client.post(
                    self._endpoint,
                    params={"grant_type": "password"},
                    headers={"apikey": self._chiave},
                    json={"email": email, "password": password},
                )
        except httpx2.RequestError as errore:  # include i timeout
            log.warning("Supabase Auth non raggiungibile: %s", type(errore).__name__)
            return ServizioNonDisponibile()

        stato = risposta.status_code
        if stato >= 500 or stato == STATO_TROPPE_RICHIESTE:
            log.warning("Supabase Auth ha risposto %s", stato)
            return ServizioNonDisponibile()
        if stato >= 400:
            return CredenzialiErrate()
        return _identita(risposta)


def _identita(risposta: httpx2.Response) -> Identita | ServizioNonDisponibile:
    try:
        utente = risposta.json()["user"]
        return Identita(user_id=uuid.UUID(utente["id"]), email=str(utente["email"]))
    except (ValueError, KeyError, TypeError):
        log.warning("Risposta di Supabase Auth in forma inattesa (stato %s)", risposta.status_code)
        return ServizioNonDisponibile()
