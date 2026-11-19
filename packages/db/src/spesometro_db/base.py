"""Base dichiarativa, convenzione dei nomi e helper comuni dei modelli."""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, MetaData, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nomi deterministici: la migrazione e `alembic check` non dipendono dai nomi di Postgres.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Nome della tabella `User`. `user` è parola riservata in Postgres: `app_user`.
USER_TABLE = "app_user"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _letterali(valori: type[StrEnum]) -> str:
    return ", ".join(f"'{v.value}'" for v in valori)


def check_in(colonna: str, valori: type[StrEnum], *, nome: str | None = None) -> CheckConstraint:
    """CHECK `colonna IN (...)` con i valori di un'enumerazione di `core`.

    Il nome logico è `nome` (default: la colonna); la convenzione lo prefissa con `ck_<tabella>_`.
    """
    return CheckConstraint(f"{colonna} IN ({_letterali(valori)})", name=nome or colonna)


def check_array_in(
    colonna: str, valori: type[StrEnum], *, nome: str | None = None
) -> CheckConstraint:
    """CHECK che ogni elemento di una colonna `text[]` appartenga all'enumerazione."""
    return CheckConstraint(
        f"{colonna} <@ ARRAY[{_letterali(valori)}]::text[]", name=nome or colonna
    )


def user_id_column() -> Mapped[uuid.UUID]:
    """`user_id` non nullo con ON DELETE CASCADE verso `User`, su ogni tabella (ADR 0014)."""
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{USER_TABLE}.id", ondelete="CASCADE"),
        nullable=False,
    )


def unico_utente_id() -> UniqueConstraint:
    """`UNIQUE (user_id, id)`: il bersaglio delle chiavi esterne composte dei figli."""
    return UniqueConstraint("user_id", "id")


def fk_stesso_utente(colonna: str, tabella: str, *, set_null: bool = False) -> ForeignKeyConstraint:
    """Chiave esterna `(colonna, user_id)` verso `(tabella.id, tabella.user_id)`.

    Una riga dell'utente A non può puntare a una riga dell'utente B (ADR 0014). Con `set_null`
    alla cancellazione del genitore si annulla solo `colonna`, mai `user_id`
    (`ON DELETE SET NULL (colonna)`, Postgres 15+); senza, `CASCADE`.
    """
    return ForeignKeyConstraint(
        [colonna, "user_id"],
        [f"{tabella}.id", f"{tabella}.user_id"],
        ondelete=f"SET NULL ({colonna})" if set_null else "CASCADE",
    )
