"""Pagine `/login` e home. Registrate da `registra_pagine` con le dipendenze iniettate."""

from collections.abc import Awaitable, Callable
from typing import assert_never
from urllib.parse import urlsplit

from nicegui import app, ui
from starlette.responses import RedirectResponse

from spesometro_web.esiti import (
    CredenzialiErrate,
    Esito,
    Riuscito,
    ServizioNonDisponibile,
    TroppiTentativi,
)
from spesometro_web.orologio import Orologio
from spesometro_web.sessione import CHIAVE_EMAIL, apri_sessione, sessione_presente

type FunzioneAccesso = Callable[[str, str, str], Awaitable[Esito]]

HOME = "/"

MESSAGGIO_CREDENZIALI_ERRATE = "Email o password non corrette."
MESSAGGIO_SERVIZIO_NON_DISPONIBILE = "Servizio di accesso non disponibile. Riprova tra poco."
MESSAGGIO_TROPPI_TENTATIVI = "Troppi tentativi di accesso. Riprova più tardi."


def messaggio_per(esito: CredenzialiErrate | ServizioNonDisponibile | TroppiTentativi) -> str:
    match esito:
        case CredenzialiErrate():
            return MESSAGGIO_CREDENZIALI_ERRATE
        case ServizioNonDisponibile():
            return MESSAGGIO_SERVIZIO_NON_DISPONIBILE
        case TroppiTentativi():
            return MESSAGGIO_TROPPI_TENTATIVI
        case _:
            assert_never(esito)


def ritorno_sicuro(destinazione: str) -> str:
    """Ammette solo percorsi interni: una sola barra iniziale, nessuno schema né host."""
    if "\\" in destinazione or not destinazione.startswith("/") or destinazione.startswith("//"):
        return HOME
    parti = urlsplit(destinazione)
    if parti.scheme or parti.netloc:
        return HOME
    return destinazione


def registra_pagine(*, accedi: FunzioneAccesso, orologio: Orologio) -> None:
    @ui.page("/login")
    def login(redirect_to: str = HOME) -> RedirectResponse | None:
        if sessione_presente(app.storage.user):
            return RedirectResponse(HOME)
        client = ui.context.client.request.client
        indirizzo = client.host if client else ""

        async def prova() -> None:
            esito = await accedi(email.value, password.value, indirizzo)
            if isinstance(esito, Riuscito):
                apri_sessione(app.storage.user, esito.user_id, esito.email, orologio())
                ui.navigate.to(ritorno_sicuro(redirect_to))
                return
            errore.set_text(messaggio_per(esito))

        email = ui.input("Email").props("type=email autocomplete=username").mark("email")
        password = (
            ui.input("Password", password=True, password_toggle_button=True)
            .props("autocomplete=current-password")
            .on("keydown.enter", prova)
            .mark("password")
        )
        ui.button("Accedi", on_click=prova).mark("accedi")
        errore = ui.label().classes("text-negative").mark("errore")
        return None

    @ui.page(HOME)
    def home() -> None:
        def esci() -> None:
            app.storage.user.clear()
            ui.navigate.to("/login")

        ui.label("Spesometro").classes("text-2xl")
        ui.label(app.storage.user[CHIAVE_EMAIL]).mark("email-utente")
        ui.button("Esci", on_click=esci).mark("esci")
