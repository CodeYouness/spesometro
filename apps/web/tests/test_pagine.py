"""Pagine /login e home con l'utente di test di NiceGUI (montaggio `ui.run_with`)."""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
from nicegui import app
from nicegui.testing import User
from spesometro_web.sessione import utente_corrente_id

UID = uuid.UUID("11111111-2222-3333-4444-555555555555")
ADESSO = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)  # come in nicegui_main.py


async def _entra(user: User, password: str, email: str = "a@b.it") -> None:
    user.find(marker="email").type(email)
    user.find(marker="password").type(password)
    user.find(marker="accedi").click()


async def test_chi_non_e_entrato_viene_portato_al_login(user: User) -> None:
    await user.open("/")

    await user.should_see(marker="accedi")


async def test_login_porta_alla_home_con_email_e_user_id_in_sessione(user: User) -> None:
    await user.open("/")

    await _entra(user, "giusta", "a@b.it")

    await user.should_see(marker="email-utente")
    await user.should_see("a@b.it")
    with user:
        assert utente_corrente_id() == UID
        sessione = dict(app.storage.user)
    assert set(sessione) == {"user_id", "email", "login_at"}
    assert isinstance(datetime.fromisoformat(sessione["login_at"]), datetime)


async def test_invio_nel_campo_password_vale_come_il_pulsante(user: User) -> None:
    await user.open("/login")
    user.find(marker="email").type("a@b.it")

    user.find(marker="password").type("giusta").trigger("keydown.enter")

    await user.should_see(marker="email-utente")


async def test_credenziali_errate_mostrano_il_messaggio_generico_senza_sessione(user: User) -> None:
    await user.open("/login")

    await _entra(user, "sbagliata")

    await user.should_see("Email o password non corrette")
    await user.should_not_see(marker="email-utente")
    with user:
        assert dict(app.storage.user) == {}
        assert utente_corrente_id() is None


async def test_servizio_non_disponibile_ha_un_messaggio_diverso(user: User) -> None:
    await user.open("/login")

    await _entra(user, "offline")

    await user.should_see("Servizio di accesso non disponibile")
    await user.should_not_see("Email o password non corrette")


async def test_troppi_tentativi_hanno_un_messaggio_proprio(user: User) -> None:
    await user.open("/login")

    await _entra(user, "bloccato")

    await user.should_see("Riprova più tardi")
    await user.should_not_see("Email o password non corrette")
    await user.should_not_see("Servizio di accesso non disponibile")


async def test_dopo_il_login_si_torna_alla_pagina_richiesta(user: User) -> None:
    await user.open("/altra?x=1")

    await user.should_see(marker="accedi")
    await _entra(user, "giusta")

    await user.should_see(marker="pagina-altra")


@pytest.mark.parametrize(
    "esterno", ["https://evil.example/x", "//evil.example/x", "/\\evil.example"]
)
async def test_ritorno_esterno_viene_scartato_e_si_va_alla_home(user: User, esterno: str) -> None:
    await user.open(f"/login?redirect_to={quote(esterno)}")

    await _entra(user, "giusta")

    await user.should_see(marker="email-utente")


async def test_login_con_sessione_valida_porta_alla_home(user: User) -> None:
    await user.open("/login")
    await _entra(user, "giusta")
    await user.should_see(marker="email-utente")

    await user.open("/login")

    await user.should_see(marker="email-utente")
    await user.should_not_see(marker="accedi")


async def test_uscita_svuota_la_sessione_e_porta_al_login(user: User) -> None:
    await user.open("/login")
    await _entra(user, "giusta")
    await user.should_see(marker="email-utente")

    user.find(marker="esci").click()

    await user.should_see(marker="accedi")
    with user:
        assert dict(app.storage.user) == {}
    await user.open("/")
    await user.should_see(marker="accedi")


async def _entra_e_sposta_login(user: User, giorni_fa: float) -> None:
    await user.open("/login")
    await _entra(user, "giusta")
    await user.should_see(marker="email-utente")
    with user:
        app.storage.user["login_at"] = (ADESSO - timedelta(days=giorni_fa)).isoformat()


async def test_sessione_di_29_giorni_vale_ancora(user: User) -> None:
    await _entra_e_sposta_login(user, 29)

    await user.open("/altra")

    await user.should_see(marker="pagina-altra")


async def test_sessione_di_oltre_30_giorni_rimanda_al_login_e_viene_svuotata(user: User) -> None:
    await _entra_e_sposta_login(user, 30.001)

    await user.open("/altra?x=1")

    await user.should_see(marker="accedi")
    with user:
        assert dict(app.storage.user) == {}
    user.find(marker="email").type("a@b.it")
    user.find(marker="password").type("giusta")
    user.find(marker="accedi").click()
    await user.should_see(marker="pagina-altra")


async def test_login_con_sessione_scaduta_mostra_il_form(user: User) -> None:
    await _entra_e_sposta_login(user, 31)

    await user.open("/login")

    await user.should_see(marker="accedi")
    await user.should_not_see(marker="email-utente")
