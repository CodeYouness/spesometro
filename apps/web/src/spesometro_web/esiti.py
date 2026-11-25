"""Esiti dell'accesso."""

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Riuscito:
    """Solo identificativo ed email: mai token."""

    user_id: uuid.UUID
    email: str


@dataclass(frozen=True)
class CredenzialiErrate:
    """Credenziali errate o account senza `User`: stesso esito, stesso messaggio."""


@dataclass(frozen=True)
class ServizioNonDisponibile:
    """Timeout, rete, 5xx, 429 o risposta anomala di Supabase Auth."""


@dataclass(frozen=True)
class TroppiTentativi:
    """Limite per indirizzo raggiunto: Supabase non viene chiamato."""


type Esito = Riuscito | CredenzialiErrate | ServizioNonDisponibile | TroppiTentativi
