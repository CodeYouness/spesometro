"""Sessione in `app.storage.user`: solo `user_id`, email e istante del login.

L'istante è una stringa ISO 8601 con fuso UTC: il ticket 04 la confronta con
`orologio()` nel middleware (scadenza a 30 giorni) tramite `istante_login`.
"""

import uuid
from collections.abc import MutableMapping
from datetime import datetime
from typing import Any

from nicegui import app

CHIAVE_USER_ID = "user_id"
CHIAVE_EMAIL = "email"
CHIAVE_LOGIN = "login_at"


def apri_sessione(
    sessione: MutableMapping[str, Any], user_id: uuid.UUID, email: str, adesso: datetime
) -> None:
    sessione.update(
        {CHIAVE_USER_ID: str(user_id), CHIAVE_EMAIL: email, CHIAVE_LOGIN: adesso.isoformat()}
    )


def sessione_presente(sessione: MutableMapping[str, Any]) -> bool:
    return bool(sessione.get(CHIAVE_USER_ID))


def istante_login(sessione: MutableMapping[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(sessione[CHIAVE_LOGIN])
    except (KeyError, TypeError, ValueError):
        return None


def utente_corrente_id() -> uuid.UUID | None:
    """Punto unico per lo `user_id` dell'utente corrente (nel contesto di una richiesta/pagina)."""
    valore = app.storage.user.get(CHIAVE_USER_ID)
    return uuid.UUID(valore) if valore else None
