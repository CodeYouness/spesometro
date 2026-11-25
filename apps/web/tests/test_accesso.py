"""Funzione di accesso: Supabase Auth finto con httpx2-pytest, nessuna rete."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from spesometro_web.accesso import accedi
from spesometro_web.esiti import (
    CredenzialiErrate,
    Riuscito,
    ServizioNonDisponibile,
    TroppiTentativi,
)
from spesometro_web.limite import LimiteTentativi
from spesometro_web.supabase_auth import ClienteSupabaseAuth

URL = "https://prog.supabase.co/auth/v1/token?grant_type=password"
UID = uuid.UUID("11111111-2222-3333-4444-555555555555")
RISPOSTA_OK = {
    "access_token": "AT-segreto",
    "refresh_token": "RT-segreto",
    "token_type": "bearer",
    "user": {"id": str(UID), "email": "a@b.it", "role": "authenticated"},
}


class Ammessi:
    def __init__(self, *ammessi: uuid.UUID) -> None:
        self.ammessi = set(ammessi)
        self.chiamate = 0

    async def __call__(self, user_id: uuid.UUID) -> bool:
        self.chiamate += 1
        return user_id in self.ammessi


class Orologio:
    def __init__(self) -> None:
        self.adesso = datetime(2026, 11, 25, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.adesso

    def avanza(self, **delta: float) -> None:
        self.adesso += timedelta(**delta)


def _accedi(
    ammesso: Ammessi,
    email: str = "a@b.it",
    password: str = "pw",
    *,
    indirizzo: str = "127.0.0.1",
    limite: LimiteTentativi | None = None,
    orologio: Orologio | None = None,
):
    return accedi(
        email,
        password,
        indirizzo,
        supabase=ClienteSupabaseAuth("https://prog.supabase.co", "sb_publishable_x"),
        ammesso=ammesso,
        orologio=orologio or Orologio(),
        limite=limite or LimiteTentativi(),
    )


async def test_credenziali_valide_danno_user_id_ed_email(httpx2_mock) -> None:
    httpx2_mock.add_response(method="POST", url=URL, json=RISPOSTA_OK)

    esito = await _accedi(Ammessi(UID))

    assert esito == Riuscito(user_id=UID, email="a@b.it")
    richiesta = httpx2_mock.get_request()
    assert richiesta.headers["apikey"] == "sb_publishable_x"
    assert richiesta.content == b'{"email":"a@b.it","password":"pw"}'


async def test_i_token_non_compaiono_nell_esito(httpx2_mock) -> None:
    httpx2_mock.add_response(method="POST", url=URL, json=RISPOSTA_OK)

    esito = await _accedi(Ammessi(UID))

    testo = repr(esito) + str(vars(esito))
    assert "segreto" not in testo


@pytest.mark.parametrize("stato", [400, 401, 422])
async def test_4xx_vale_credenziali_errate(httpx2_mock, stato: int) -> None:
    httpx2_mock.add_response(method="POST", url=URL, status_code=stato, json={"msg": "no"})

    assert await _accedi(Ammessi(UID)) == CredenzialiErrate()


@pytest.mark.parametrize("stato", [429, 500, 503])
async def test_429_e_5xx_valgono_servizio_non_disponibile(httpx2_mock, stato: int) -> None:
    httpx2_mock.add_response(method="POST", url=URL, status_code=stato, json={})

    assert await _accedi(Ammessi(UID)) == ServizioNonDisponibile()


@pytest.mark.parametrize(
    "errore", [httpx2.ReadTimeout("t"), httpx2.ConnectError("c")], ids=["timeout", "rete"]
)
async def test_timeout_ed_errore_di_rete_valgono_servizio_non_disponibile(
    httpx2_mock, errore: Exception
) -> None:
    httpx2_mock.add_exception(errore)

    assert await _accedi(Ammessi(UID)) == ServizioNonDisponibile()


@pytest.mark.parametrize(
    "corpo", [{}, {"user": {"id": str(UID)}}, {"user": {"id": "x", "email": "e"}}]
)
async def test_risposta_200_anomala_vale_servizio_non_disponibile(httpx2_mock, corpo) -> None:
    httpx2_mock.add_response(method="POST", url=URL, json=corpo)

    assert await _accedi(Ammessi(UID)) == ServizioNonDisponibile()


async def test_account_senza_user_vale_credenziali_errate(httpx2_mock) -> None:
    httpx2_mock.add_response(method="POST", url=URL, json=RISPOSTA_OK)

    assert await _accedi(Ammessi()) == CredenzialiErrate()


@pytest.mark.parametrize(("email", "password"), [("", "pw"), ("a@b.it", ""), ("", "")])
async def test_input_vuoti_sono_credenziali_errate_senza_chiamate(
    httpx2_mock, email: str, password: str
) -> None:
    ammesso = Ammessi(UID)

    assert await _accedi(ammesso, email, password) == CredenzialiErrate()
    assert not httpx2_mock.get_requests()
    assert ammesso.chiamate == 0


async def test_il_servizio_non_disponibile_non_verifica_l_ammissione(httpx2_mock) -> None:
    httpx2_mock.add_response(method="POST", url=URL, status_code=500)
    ammesso = Ammessi(UID)

    await _accedi(ammesso)

    assert ammesso.chiamate == 0


async def _falliti(httpx2_mock, n: int, **kw) -> None:
    for _ in range(n):
        httpx2_mock.add_response(method="POST", url=URL, status_code=400, json={})
    for _ in range(n):
        assert await _accedi(Ammessi(UID), **kw) == CredenzialiErrate()


async def test_il_sesto_tentativo_e_fermato_senza_chiamare_supabase(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    await _falliti(httpx2_mock, 5, limite=limite, orologio=orologio)

    esito = await _accedi(Ammessi(UID), limite=limite, orologio=orologio)

    assert esito == TroppiTentativi()
    assert len(httpx2_mock.get_requests()) == 5


async def test_il_blocco_vale_anche_con_credenziali_giuste(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    await _falliti(httpx2_mock, 5, limite=limite, orologio=orologio)
    httpx2_mock.add_response(method="POST", url=URL, json=RISPOSTA_OK, is_optional=True)

    assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == TroppiTentativi()


async def test_la_finestra_scorre_dopo_15_minuti(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    await _falliti(httpx2_mock, 5, limite=limite, orologio=orologio)

    orologio.avanza(minutes=14, seconds=59)
    assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == TroppiTentativi()

    orologio.avanza(seconds=1)
    httpx2_mock.add_response(method="POST", url=URL, status_code=400, json={})
    assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == CredenzialiErrate()


async def test_la_finestra_e_mobile_scadono_i_singoli_tentativi(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    await _falliti(httpx2_mock, 3, limite=limite, orologio=orologio)
    orologio.avanza(minutes=10)
    await _falliti(httpx2_mock, 2, limite=limite, orologio=orologio)

    assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == TroppiTentativi()
    orologio.avanza(minutes=5)  # i primi 3 escono dalla finestra, restano 2
    httpx2_mock.add_response(method="POST", url=URL, status_code=400, json={})
    assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == CredenzialiErrate()


async def test_un_accesso_riuscito_azzera_il_conteggio(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    await _falliti(httpx2_mock, 4, limite=limite, orologio=orologio)
    httpx2_mock.add_response(method="POST", url=URL, json=RISPOSTA_OK)
    assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == Riuscito(UID, "a@b.it")

    await _falliti(httpx2_mock, 5, limite=limite, orologio=orologio)
    assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == TroppiTentativi()


async def test_l_utente_non_ammesso_conta_come_fallito(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    for _ in range(5):
        httpx2_mock.add_response(method="POST", url=URL, json=RISPOSTA_OK)
        assert await _accedi(Ammessi(), limite=limite, orologio=orologio) == CredenzialiErrate()

    assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == TroppiTentativi()


async def test_il_servizio_non_disponibile_non_conta(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    for _ in range(10):
        httpx2_mock.add_response(method="POST", url=URL, status_code=503)
        assert await _accedi(Ammessi(UID), limite=limite, orologio=orologio) == (
            ServizioNonDisponibile()
        )


async def test_ogni_indirizzo_ha_il_suo_conteggio(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    await _falliti(httpx2_mock, 5, limite=limite, orologio=orologio, indirizzo="1.1.1.1")

    httpx2_mock.add_response(method="POST", url=URL, status_code=400, json={})
    esito = await _accedi(Ammessi(UID), limite=limite, orologio=orologio, indirizzo="2.2.2.2")

    assert esito == CredenzialiErrate()


async def test_il_blocco_vale_anche_per_input_vuoti(httpx2_mock) -> None:
    limite, orologio = LimiteTentativi(), Orologio()
    await _falliti(httpx2_mock, 5, limite=limite, orologio=orologio)

    assert await _accedi(Ammessi(UID), "", "", limite=limite, orologio=orologio) == (
        TroppiTentativi()
    )
