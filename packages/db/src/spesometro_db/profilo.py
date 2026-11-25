"""Profilo `User`: comando del proprietario e verifica di ammissione.

Uso: `uv run python -m spesometro_db.profilo <uuid-account-supabase-auth>`
(connessione via `DATABASE_URL`, session pooler 5432: ADR 0001).
"""

import argparse
import asyncio
import sys
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spesometro_db.engine import create_engine, create_session_factory
from spesometro_db.models import User


async def utente_ammesso(
    session_factory: async_sessionmaker[AsyncSession], user_id: uuid.UUID
) -> bool:
    """Esiste un `User` con questo identificativo? Sola lettura."""
    async with session_factory() as session:
        trovato = await session.scalar(select(User.id).where(User.id == user_id))
    return trovato is not None


async def crea_profilo(
    session_factory: async_sessionmaker[AsyncSession], user_id: uuid.UUID
) -> bool:
    """Crea il `User` coi valori predefiniti. `False` se esisteva già (nessun effetto)."""
    async with session_factory() as session, session.begin():
        creato = await session.scalar(
            insert(User)
            .values(id=user_id)
            .on_conflict_do_nothing(index_elements=[User.id])
            .returning(User.id)
        )
    return creato is not None


async def _crea(user_id: uuid.UUID) -> bool:
    engine = create_engine(pool_size=1)
    try:
        return await crea_profilo(create_session_factory(engine), user_id)
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="spesometro_db.profilo", description="Crea il User di un account Supabase Auth."
    )
    parser.add_argument("user_id", help="UUID dell'account Supabase Auth")
    args = parser.parse_args(argv)
    try:
        user_id = uuid.UUID(args.user_id)
    except ValueError:
        print(f"Errore: '{args.user_id}' non è un UUID valido.", file=sys.stderr)
        return 2
    if asyncio.run(_crea(user_id)):
        print(f"User {user_id} creato.")
    else:
        print(f"User {user_id} esiste già: nessuna modifica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
