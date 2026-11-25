"""Funzione di accesso: Supabase Auth finto con httpx2-pytest, nessuna rete."""

import uuid
from datetime import UTC, datetime

import httpx2
import pytest
from spesometro_web.accesso import accedi
from spesometro_web.esiti import CredenzialiErrate, Riuscito, ServizioNonDisponibile
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


def _accedi(ammesso: Ammessi, email: str = "a@b.it", password: str = "pw"):
    return accedi(
        email,
        password,
        "127.0.0.1",
        supabase=ClienteSupabaseAuth("https://prog.supabase.co", "sb_publishable_x"),
        ammesso=ammesso,
        orologio=lambda: datetime(2026, 11, 25, tzinfo=UTC),
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
