"""Modelli SQLAlchemy. Ogni tabella ha `user_id` (tranne `app_user`), vedi `user_id_column`."""

import uuid
from decimal import Decimal

from spesometro_core import Attributo, Catena, TipoEsclusione
from sqlalchemy import Numeric, PrimaryKeyConstraint, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from spesometro_db.base import (
    USER_TABLE,
    Base,
    check_array_in,
    check_in,
    user_id_column,
)


class User(Base):
    """Stesso UUID dell'utente Supabase Auth; nessuna chiave esterna verso `auth`."""

    __tablename__ = USER_TABLE
    __table_args__ = (
        check_array_in("carte_fedelta", Catena),
        check_in("catena_abituale", Catena),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    carte_fedelta: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    catena_abituale: Mapped[str | None] = mapped_column(Text)
    insegna_coop: Mapped[str | None] = mapped_column(Text)
    risparmio_minimo_per_negozio: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, server_default=text("5")
    )
    max_negozi: Mapped[int] = mapped_column(nullable=False, server_default=text("2"))


class Exclusion(Base):
    __tablename__ = "exclusion"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "attributo"),
        check_in("attributo", Attributo),
        check_in("tipo", TipoEsclusione),
    )

    user_id: Mapped[uuid.UUID] = user_id_column()
    attributo: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
