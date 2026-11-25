"""Middleware di autenticazione (`BaseHTTPMiddleware` + `app.storage.user`).

La sessione scade 30 giorni dopo il login (istante salvato in sessione, nessuna lettura
del database): una sessione scaduta o senza istante valido viene svuotata e trattata come assente.
"""

from datetime import timedelta
from urllib.parse import quote

from nicegui import app
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp

from spesometro_web.orologio import Orologio
from spesometro_web.sessione import istante_login, sessione_presente

# Lista unica dei percorsi pubblici (aggiungere qui, ad es., il webhook Telegram).
PERCORSI_PUBBLICI = frozenset({"/login", "/health", "/favicon.ico"})
# Asset statici e socket.io di NiceGUI (`/_nicegui/...`, `/_nicegui_ws/...`).
PREFISSI_PUBBLICI = ("/_nicegui",)
DURATA_SESSIONE = timedelta(days=30)


def percorso_pubblico(percorso: str) -> bool:
    return percorso in PERCORSI_PUBBLICI or percorso.startswith(PREFISSI_PUBBLICI)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app_: ASGIApp, *, orologio: Orologio) -> None:
        super().__init__(app_)
        self._orologio = orologio

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith(PREFISSI_PUBBLICI):
            self._scarta_se_scaduta()
        if percorso_pubblico(request.url.path) or sessione_presente(app.storage.user):
            return await call_next(request)
        richiesto = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"/login?redirect_to={quote(richiesto, safe='')}")

    def _scarta_se_scaduta(self) -> None:
        sessione = app.storage.user
        if not sessione_presente(sessione):
            return
        login = istante_login(sessione)
        if login is None or self._orologio() - login >= DURATA_SESSIONE:
            sessione.clear()
