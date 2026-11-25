from functools import partial

from fastapi import FastAPI
from spesometro_db import create_engine, create_session_factory, utente_ammesso
from spesometro_web import mount_ui, orologio_utc
from spesometro_web.accesso import accedi
from spesometro_web.config import Impostazioni
from spesometro_web.supabase_auth import ClienteSupabaseAuth

# Senza una variabile obbligatoria l'app non parte e l'errore la nomina.
impostazioni = Impostazioni.da_ambiente()

app = FastAPI(title="Spesometro")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Un solo engine condiviso (pool entro il limite di `spesometro_db`).
_session_factory = create_session_factory(create_engine(impostazioni.database_url, pool_size=3))


# Le route FastAPI vanno registrate prima del mount: NiceGUI occupa "/".
mount_ui(
    app,
    storage_secret=impostazioni.storage_secret,
    accedi=partial(
        accedi,
        supabase=ClienteSupabaseAuth(
            impostazioni.supabase_url, impostazioni.supabase_chiave_pubblicabile
        ),
        ammesso=partial(utente_ammesso, _session_factory),
        orologio=orologio_utc,
    ),
    orologio=orologio_utc,
)
