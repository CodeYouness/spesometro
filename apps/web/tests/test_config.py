import pytest
from spesometro_web.config import Impostazioni

COMPLETE = {
    "SUPABASE_URL": "https://prog.supabase.co",
    "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_x",
    "DATABASE_URL": "postgresql://u:p@h:5432/db",
    "NICEGUI_STORAGE_SECRET": "s",
}


def test_legge_le_variabili() -> None:
    impostazioni = Impostazioni.da_ambiente(COMPLETE)

    assert impostazioni.supabase_url == "https://prog.supabase.co"
    assert impostazioni.supabase_chiave_pubblicabile == "sb_publishable_x"
    assert impostazioni.database_url == "postgresql://u:p@h:5432/db"
    assert impostazioni.storage_secret == "s"


@pytest.mark.parametrize("mancante", list(COMPLETE))
@pytest.mark.parametrize("vuota", [False, True])
def test_variabile_mancante_o_vuota_ferma_l_avvio_nominandola(mancante: str, vuota: bool) -> None:
    ambiente = {k: v for k, v in COMPLETE.items() if k != mancante}
    if vuota:
        ambiente[mancante] = ""

    with pytest.raises(RuntimeError, match=mancante):
        Impostazioni.da_ambiente(ambiente)
