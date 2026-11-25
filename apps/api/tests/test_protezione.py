"""Protezione delle pagine via HTTP sull'app vera (nessuna rete: l'engine non si connette)."""

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from spesometro_api.main import app


@pytest.fixture
def client():
    with TestClient(app, follow_redirects=False) as client:
        yield client


def test_senza_sessione_si_viene_rimandati_al_login_col_percorso_di_ritorno(client) -> None:
    risposta = client.get("/qualcosa?a=1&b=2")

    assert risposta.status_code in (302, 307)
    posizione = urlsplit(risposta.headers["location"])
    assert posizione.path == "/login"
    assert parse_qs(posizione.query) == {"redirect_to": ["/qualcosa?a=1&b=2"]}


def test_la_home_senza_sessione_rimanda_al_login(client) -> None:
    risposta = client.get("/")

    assert urlsplit(risposta.headers["location"]).path == "/login"


@pytest.mark.parametrize("percorso", ["/health", "/login"])
def test_percorsi_pubblici_rispondono_senza_sessione(client, percorso: str) -> None:
    assert client.get(percorso).status_code == 200


def test_gli_asset_interni_di_nicegui_non_sono_rimandati_al_login(client) -> None:
    risposta = client.get("/_nicegui/0/qualcosa-che-non-esiste")

    assert "location" not in risposta.headers
