"""Apertura della sessione: contiene esattamente `user_id`, email e istante del login."""

import uuid
from datetime import UTC, datetime

from spesometro_web.sessione import apri_sessione

UID = uuid.UUID("11111111-2222-3333-4444-555555555555")


def test_apri_sessione_scarta_i_residui_di_una_sessione_precedente() -> None:
    sessione = {"residuo": "x", "user_id": "altro"}

    apri_sessione(sessione, UID, "a@b.it", datetime(2026, 11, 25, tzinfo=UTC))

    assert sessione == {
        "user_id": str(UID),
        "email": "a@b.it",
        "login_at": "2026-11-25T00:00:00+00:00",
    }
