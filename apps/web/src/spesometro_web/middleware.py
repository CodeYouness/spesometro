"""Middleware di autenticazione (`BaseHTTPMiddleware` + `app.storage.user`).

Il ticket 04 aggiunge qui la scadenza a 30 giorni: confronta `istante_login(...)`
con `self._orologio()`, svuota la sessione scaduta e la tratta come assente.
"""

from urllib.parse import quote

from nicegui import app
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp

from spesometro_web.accesso import Orologio
from spesometro_web.sessione import sessione_presente

# Lista unica dei percorsi pubblici (aggiungere qui, ad es., il webhook Telegram).
PERCORSI_PUBBLICI = frozenset({"/login", "/health", "/favicon.ico"})
# Asset statici e socket.io di NiceGUI (`/_nicegui/...`, `/_nicegui_ws/...`).
PREFISSI_PUBBLICI = ("/_nicegui",)


def percorso_pubblico(percorso: str) -> bool:
    return percorso in PERCORSI_PUBBLICI or percorso.startswith(PREFISSI_PUBBLICI)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app_: ASGIApp, *, orologio: Orologio) -> None:
        super().__init__(app_)
        self._orologio = orologio

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if percorso_pubblico(request.url.path) or sessione_presente(app.storage.user):
            return await call_next(request)
        richiesto = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?redirect_to={quote(richiesto, safe='')}")
