"""Limite dei tentativi: gli indirizzi con finestra interamente scaduta non restano in memoria."""

from datetime import UTC, datetime, timedelta

from spesometro_web.limite import FINESTRA, LimiteTentativi

T0 = datetime(2026, 11, 25, tzinfo=UTC)


def test_gli_indirizzi_scaduti_e_mai_tornati_vengono_eliminati() -> None:
    limite = LimiteTentativi()
    limite.registra_fallito("1.1.1.1", T0)

    limite.registra_fallito("2.2.2.2", T0 + FINESTRA)

    assert limite.indirizzi_tracciati() == {"2.2.2.2"}


def test_gli_indirizzi_con_tentativi_ancora_in_finestra_restano() -> None:
    limite = LimiteTentativi()
    limite.registra_fallito("1.1.1.1", T0)

    limite.registra_fallito("2.2.2.2", T0 + FINESTRA - timedelta(seconds=1))

    assert limite.indirizzi_tracciati() == {"1.1.1.1", "2.2.2.2"}
