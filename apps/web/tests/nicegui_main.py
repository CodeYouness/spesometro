"""Main file per l'utente di test di NiceGUI (opzione `main_file` in pyproject).

Rieseguito a ogni test: monta la UI con una funzione di accesso finta, deterministica
sulla password (`giusta`, `offline`, `bloccato`, qualunque altra cosa = credenziali errate).
L'orologio è fisso: i test che lo spostano scrivono in sessione.
"""

import uuid
from datetime import UTC, datetime

from fastapi import FastAPI
from nicegui import ui
from spesometro_web import mount_ui
from spesometro_web.esiti import (
    CredenzialiErrate,
    Esito,
    Riuscito,
    ServizioNonDisponibile,
    TroppiTentativi,
)

UID = uuid.UUID("11111111-2222-3333-4444-555555555555")
ADESSO = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


async def accedi_finto(email: str, password: str, indirizzo: str) -> Esito:
    if password == "giusta":
        return Riuscito(user_id=UID, email=email)
    if password == "offline":
        return ServizioNonDisponibile()
    if password == "bloccato":
        return TroppiTentativi()
    return CredenzialiErrate()


fastapi_app = FastAPI()


@fastapi_app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


mount_ui(
    fastapi_app, storage_secret="solo-per-i-test", accedi=accedi_finto, orologio=lambda: ADESSO
)


@ui.page("/altra")
def altra() -> None:
    ui.label("Un'altra pagina protetta").mark("pagina-altra")
