"""Configurazione da variabili d'ambiente: l'app non parte se ne manca una."""

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Impostazioni:
    supabase_url: str
    supabase_chiave_pubblicabile: str
    database_url: str
    storage_secret: str

    @classmethod
    def da_ambiente(cls, ambiente: Mapping[str, str] | None = None) -> "Impostazioni":
        ambiente = os.environ if ambiente is None else ambiente

        def richiesta(nome: str) -> str:
            valore = ambiente.get(nome, "")
            if not valore:
                raise RuntimeError(f"Variabile d'ambiente mancante: {nome}")
            return valore

        return cls(
            supabase_url=richiesta("SUPABASE_URL"),
            supabase_chiave_pubblicabile=richiesta("SUPABASE_PUBLISHABLE_KEY"),
            database_url=richiesta("DATABASE_URL"),
            storage_secret=richiesta("NICEGUI_STORAGE_SECRET"),
        )
