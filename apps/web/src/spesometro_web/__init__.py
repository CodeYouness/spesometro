"""UI NiceGUI di Spesometro."""

from fastapi import FastAPI
from nicegui import ui


@ui.page("/")
def index() -> None:
    ui.label("Hello, Spesometro").classes("text-2xl")


def mount_ui(app: FastAPI, *, storage_secret: str) -> None:
    """Monta la UI sull'app FastAPI: un solo processo, un solo worker (SPEC §7)."""
    ui.run_with(
        app,
        mount_path="/",
        storage_secret=storage_secret,
        title="Spesometro",
        language="it",
    )
