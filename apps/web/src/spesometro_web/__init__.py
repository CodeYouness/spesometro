"""UI NiceGUI di Spesometro."""

from datetime import UTC, datetime

from fastapi import FastAPI
from nicegui import app as nicegui_app
from nicegui import ui

from spesometro_web.accesso import Orologio
from spesometro_web.middleware import AuthMiddleware
from spesometro_web.pagine import FunzioneAccesso, registra_pagine


def orologio_utc() -> datetime:
    return datetime.now(UTC)


def mount_ui(
    app: FastAPI,
    *,
    storage_secret: str,
    accedi: FunzioneAccesso,
    orologio: Orologio = orologio_utc,
) -> None:
    """Monta la UI sull'app FastAPI: un solo processo, un solo worker (SPEC §7)."""
    registra_pagine(accedi=accedi, orologio=orologio)
    # Prima di `run_with`: così SessionMiddleware di NiceGUI è più esterno e
    # `app.storage.user` funziona dentro il middleware.
    nicegui_app.add_middleware(AuthMiddleware, orologio=orologio)
    ui.run_with(
        app,
        mount_path="/",
        storage_secret=storage_secret,
        title="Spesometro",
        language="it",
    )
