"""Modelli SQLAlchemy. Ogni tabella ha `user_id` (tranne `app_user`), vedi `user_id_column`."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from spesometro_core import (
    Attributo,
    Catena,
    CondizioneOfferta,
    Fonte,
    LivelloConfidenza,
    StatoJob,
    StatoProvenienza,
    TipoDurata,
    TipoEsclusione,
    TipoVolantino,
    UnitaBase,
    UnitaDiVendita,
)
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from spesometro_db.base import (
    USER_TABLE,
    Base,
    check_array_in,
    check_in,
    fk_stesso_utente,
    unico_utente_id,
    user_id_column,
)


def _uuid_ref(*, nullable: bool = False) -> Mapped[uuid.UUID]:
    """Colonna UUID che punta a un'altra riga dello stesso utente (vedi `fk_stesso_utente`)."""
    return mapped_column(UUID(as_uuid=True), nullable=nullable)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Provenienza:
    """Mixin delle cinque colonne di provenienza (ADR 0014).

    Solo su Offer, ReceiptLine, ProductAlias, Product, GroupAlternative. I CHECK si aggiungono
    con `vincoli_provenienza()` in `__table_args__`. `fonte_id` non ha chiave esterna: punta
    a un volantino o a uno scontrino a seconda della `fonte`.
    """

    fonte: Mapped[str] = mapped_column(Text, nullable=False)
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    acquisito_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confidenza: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    stato: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text(f"'{StatoProvenienza.AUTO.value}'")
    )


def vincoli_provenienza() -> tuple[CheckConstraint, ...]:
    return (
        check_in("fonte", Fonte),
        check_in("stato", StatoProvenienza),
        CheckConstraint("confidenza >= 0 AND confidenza <= 1", name="confidenza"),
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


class ProductGroup(Base):
    """Il bisogno su cui lavorano magazzino, lista e confronto prezzi (ADR 0005)."""

    __tablename__ = "product_group"
    __table_args__ = (
        unico_utente_id(),
        check_in("unita_base", UnitaBase),
        check_in("tipo_durata", TipoDurata),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    categoria: Mapped[str | None] = mapped_column(Text)
    unita_base: Mapped[str] = mapped_column(Text, nullable=False)
    # Formato normalizzato di riferimento, espresso in `unita_base`.
    formato_riferimento: Mapped[Decimal | None] = mapped_column(Numeric)
    tipo_durata: Mapped[str] = mapped_column(Text, nullable=False)
    durata_tipica_giorni: Mapped[int | None] = mapped_column()


class Product(Provenienza, Base):
    __tablename__ = "product"
    __table_args__ = (
        unico_utente_id(),
        fk_stesso_utente("group_id", "product_group", set_null=True),
        check_in("unita_base", UnitaBase),
        check_in("unita_di_vendita", UnitaDiVendita),
        check_array_in("attributi", Attributo),
        CheckConstraint("dimensione_base > 0", name="dimensione_base_positiva"),
        *vincoli_provenienza(),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    marca: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[uuid.UUID | None] = _uuid_ref(nullable=True)
    unita_di_vendita: Mapped[str] = mapped_column(Text, nullable=False)
    # Dimensione come stampata (unita libera) e normalizzata in `unita_base`.
    dimensione_originale_quantita: Mapped[Decimal | None] = mapped_column(Numeric)
    dimensione_originale_unita: Mapped[str | None] = mapped_column(Text)
    dimensione_base: Mapped[Decimal | None] = mapped_column(Numeric)
    unita_base: Mapped[str | None] = mapped_column(Text)
    attributi: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    attributi_verificati: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))


class ProductAlias(Provenienza, Base):
    __tablename__ = "product_alias"
    __table_args__ = (
        fk_stesso_utente("product_id", "product"),
        check_in("catena", Catena),
        *vincoli_provenienza(),
        # Una stringa grezza per catena punta a un solo Product valido; i rifiutati restano.
        Index(
            "uq_product_alias_user_id_catena_testo_grezzo",
            "user_id",
            "catena",
            "testo_grezzo",
            unique=True,
            postgresql_where=text(f"stato <> '{StatoProvenienza.RIFIUTATO.value}'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    testo_grezzo: Mapped[str] = mapped_column(Text, nullable=False)
    catena: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[uuid.UUID] = _uuid_ref()


class GroupAlternative(Provenienza, Base):
    """`group_b` e alternativa di `group_a`, in questo verso (la regola non si inverte da sola)."""

    __tablename__ = "group_alternative"
    __table_args__ = (
        UniqueConstraint("user_id", "group_a", "group_b"),
        fk_stesso_utente("group_a", "product_group"),
        fk_stesso_utente("group_b", "product_group"),
        CheckConstraint("group_a <> group_b", name="gruppi_diversi"),
        *vincoli_provenienza(),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    group_a: Mapped[uuid.UUID] = _uuid_ref()
    group_b: Mapped[uuid.UUID] = _uuid_ref()


class Flyer(Base):
    """Volantino. Lo stesso file (`sha256`) non entra due volte per lo stesso utente."""

    __tablename__ = "flyer"
    __table_args__ = (
        unico_utente_id(),
        UniqueConstraint("user_id", "sha256"),
        check_in("catena", Catena),
        check_in("tipo", TipoVolantino),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    catena: Mapped[str] = mapped_column(Text, nullable=False)
    insegna: Mapped[str | None] = mapped_column(Text)
    zona: Mapped[str | None] = mapped_column(Text)
    validita_da: Mapped[date] = mapped_column(Date, nullable=False)
    validita_a: Mapped[date] = mapped_column(Date, nullable=False)
    # `catalogo` = listino: i suoi prezzi non sono promozioni (vista PriceObservation).
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    numero_pagine: Mapped[int | None] = mapped_column()
    url_origine: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    incluso: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))


class Offer(Provenienza, Base):
    __tablename__ = "offer"
    __table_args__ = (
        fk_stesso_utente("flyer_id", "flyer"),
        fk_stesso_utente("product_id", "product", set_null=True),
        check_in("condizione", CondizioneOfferta),
        check_in("unita", UnitaBase),
        *vincoli_provenienza(),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    flyer_id: Mapped[uuid.UUID] = _uuid_ref()
    pagina: Mapped[int | None] = mapped_column()
    testo_grezzo: Mapped[str] = mapped_column(Text, nullable=False)
    product_id: Mapped[uuid.UUID | None] = _uuid_ref(nullable=True)
    prezzo_confezione: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    # Prezzo per `unita`; con `multi_acquisto` è quello effettivo a `quantita_minima`.
    prezzo_unitario: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    unita: Mapped[str | None] = mapped_column(Text)
    prezzo_barrato: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sconto_dichiarato: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    validita_da: Mapped[date | None] = mapped_column(Date)
    validita_a: Mapped[date | None] = mapped_column(Date)
    condizione: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text(f"'{CondizioneOfferta.NESSUNA.value}'")
    )
    quantita_minima: Mapped[int | None] = mapped_column()
    limite_pezzi: Mapped[int | None] = mapped_column()


class Receipt(Base):
    """Scontrino. Data e ora come stampate (senza fuso); chiave naturale per non duplicarlo."""

    __tablename__ = "receipt"
    __table_args__ = (
        unico_utente_id(),
        UniqueConstraint("user_id", "catena", "data_ora", "totale"),
        check_in("catena", Catena),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    data_ora: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    catena: Mapped[str] = mapped_column(Text, nullable=False)
    totale: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    impronta: Mapped[str | None] = mapped_column(Text)
    estrazione_grezza: Mapped[dict | None] = mapped_column(JSONB)


class ReceiptLine(Provenienza, Base):
    """Riga di scontrino. Il prezzo unitario non si salva: lo calcola la vista."""

    __tablename__ = "receipt_line"
    __table_args__ = (
        fk_stesso_utente("receipt_id", "receipt"),
        fk_stesso_utente("product_id", "product", set_null=True),
        CheckConstraint("quantita > 0", name="quantita_positiva"),
        *vincoli_provenienza(),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    receipt_id: Mapped[uuid.UUID] = _uuid_ref()
    testo_grezzo: Mapped[str] = mapped_column(Text, nullable=False)
    # Pezzi o kg (peso variabile).
    quantita: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    # Totale di riga prima dello sconto; `sconto` è un importo (positivo).
    prezzo: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sconto: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default=text("0")
    )
    product_id: Mapped[uuid.UUID | None] = _uuid_ref(nullable=True)


class InventoryItem(Base):
    """Stima di quanto resta in casa di un gruppo: una sola riga per (utente, gruppo)."""

    __tablename__ = "inventory_item"
    __table_args__ = (
        UniqueConstraint("user_id", "group_id"),
        fk_stesso_utente("group_id", "product_group"),
        CheckConstraint("livello IN (0, 1, 2)", name="livello"),
        check_in("livello_confidenza", LivelloConfidenza),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    group_id: Mapped[uuid.UUID] = _uuid_ref()
    data_ultimo_acquisto: Mapped[date | None] = mapped_column(Date)
    # In `unita_base` del gruppo.
    quantita_ultimo_acquisto: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    # `unita_base` al giorno; NULL ai livelli bassi (stima dalla durata tipica).
    tasso_consumo: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    durata_stimata_giorni: Mapped[int | None] = mapped_column()
    # Scadenza reale inserita a mano (gruppi `scadenza_reale`).
    scadenza_reale: Mapped[date | None] = mapped_column(Date)
    probabilmente_finito: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    livello: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    livello_confidenza: Mapped[str] = mapped_column(Text, nullable=False)


class Job(Base):
    """Lavoro in background con stato, tentativi e lease (la coda arriva in un altro ticket)."""

    __tablename__ = "job"
    __table_args__ = (check_in("stato", StatoJob),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = user_id_column()
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    stato: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text(f"'{StatoJob.PENDING.value}'")
    )
    tentativi: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    lease_scade_il: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
