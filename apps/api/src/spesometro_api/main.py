import os

from fastapi import FastAPI
from spesometro_web import mount_ui

app = FastAPI(title="Spesometro")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Le route FastAPI vanno registrate prima del mount: NiceGUI occupa "/".
mount_ui(app, storage_secret=os.environ["NICEGUI_STORAGE_SECRET"])
