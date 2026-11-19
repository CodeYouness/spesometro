"""iniziale: User, Exclusion, catalogo, provenienza, fonti dei prezzi, pg_trgm, RLS senza policy

Migrazione iniziale e unica dello schema (spec schema-dati): i ticket 02-05 la estendono
aggiungendo `op.create_table` dopo quelle esistenti e il nome della tabella in `TABELLE`.

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401  (le migrazioni autogenerate possono referenziarlo)
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Ogni tabella creata qui riceve la RLS senza policy (ADR 0014 punto 5). Ordine: genitori prima.
TABELLE = [
    "app_user",
    "exclusion",
    "product_group",
    "product",
    "product_alias",
    "group_alternative",
    "flyer",
    "offer",
    "receipt",
    "receipt_line",
    "inventory_item",
    "job",
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "app_user",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "carte_fedelta",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("catena_abituale", sa.Text(), nullable=True),
        sa.Column("insegna_coop", sa.Text(), nullable=True),
        sa.Column(
            "risparmio_minimo_per_negozio",
            sa.Numeric(precision=8, scale=2),
            server_default=sa.text("5"),
            nullable=False,
        ),
        sa.Column("max_negozi", sa.Integer(), server_default=sa.text("2"), nullable=False),
        sa.CheckConstraint(
            "carte_fedelta <@ ARRAY['lidl', 'eurospin', 'coop', 'altra']::text[]",
            name=op.f("ck_app_user_carte_fedelta"),
        ),
        sa.CheckConstraint(
            "catena_abituale IN ('lidl', 'eurospin', 'coop', 'altra')",
            name=op.f("ck_app_user_catena_abituale"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
    )
    op.create_table(
        "exclusion",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("attributo", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "attributo IN ('maiale', 'carne', 'pesce', 'alcol', 'glutine', 'lattosio',"
            " 'frutta_a_guscio')",
            name=op.f("ck_exclusion_attributo"),
        ),
        sa.CheckConstraint("tipo IN ('allergia', 'dieta')", name=op.f("ck_exclusion_tipo")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_exclusion_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "attributo", name=op.f("pk_exclusion")),
    )

    op.create_table(
        "product_group",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("categoria", sa.Text(), nullable=True),
        sa.Column("unita_base", sa.Text(), nullable=False),
        sa.Column("formato_riferimento", sa.Numeric(), nullable=True),
        sa.Column("tipo_durata", sa.Text(), nullable=False),
        sa.Column("durata_tipica_giorni", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "tipo_durata IN ('scadenza_reale', 'durata_stimata', 'non_deperibile')",
            name=op.f("ck_product_group_tipo_durata"),
        ),
        sa.CheckConstraint(
            "unita_base IN ('kg', 'L', 'pezzo')", name=op.f("ck_product_group_unita_base")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_product_group_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_group")),
    )
    op.create_table(
        "product",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("marca", sa.Text(), nullable=True),
        sa.Column("group_id", sa.UUID(), nullable=True),
        sa.Column("unita_di_vendita", sa.Text(), nullable=False),
        sa.Column("dimensione_originale_quantita", sa.Numeric(), nullable=True),
        sa.Column("dimensione_originale_unita", sa.Text(), nullable=True),
        sa.Column("dimensione_base", sa.Numeric(), nullable=True),
        sa.Column("unita_base", sa.Text(), nullable=True),
        sa.Column(
            "attributi",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "attributi_verificati", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("fonte", sa.Text(), nullable=False),
        sa.Column("fonte_id", sa.UUID(), nullable=True),
        sa.Column(
            "acquisito_il",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confidenza", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("stato", sa.Text(), server_default=sa.text("'auto'"), nullable=False),
        sa.CheckConstraint(
            "attributi <@ ARRAY['maiale', 'carne', 'pesce', 'alcol', 'glutine', 'lattosio',"
            " 'frutta_a_guscio']::text[]",
            name=op.f("ck_product_attributi"),
        ),
        sa.CheckConstraint(
            "fonte IN ('volantino', 'scontrino', 'umano', 'regola')", name=op.f("ck_product_fonte")
        ),
        sa.CheckConstraint(
            "stato IN ('auto', 'rivisto', 'rifiutato')", name=op.f("ck_product_stato")
        ),
        sa.CheckConstraint(
            "unita_base IN ('kg', 'L', 'pezzo')", name=op.f("ck_product_unita_base")
        ),
        sa.CheckConstraint(
            "unita_di_vendita IN ('pezzo', 'peso_variabile')",
            name=op.f("ck_product_unita_di_vendita"),
        ),
        sa.CheckConstraint(
            "confidenza >= 0 AND confidenza <= 1", name=op.f("ck_product_confidenza")
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["product_group.id"],
            name=op.f("fk_product_group_id_product_group"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_product_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product")),
    )
    op.create_table(
        "product_alias",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("testo_grezzo", sa.Text(), nullable=False),
        sa.Column("catena", sa.Text(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("fonte", sa.Text(), nullable=False),
        sa.Column("fonte_id", sa.UUID(), nullable=True),
        sa.Column(
            "acquisito_il",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confidenza", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("stato", sa.Text(), server_default=sa.text("'auto'"), nullable=False),
        sa.CheckConstraint(
            "catena IN ('lidl', 'eurospin', 'coop', 'altra')", name=op.f("ck_product_alias_catena")
        ),
        sa.CheckConstraint(
            "fonte IN ('volantino', 'scontrino', 'umano', 'regola')",
            name=op.f("ck_product_alias_fonte"),
        ),
        sa.CheckConstraint(
            "stato IN ('auto', 'rivisto', 'rifiutato')", name=op.f("ck_product_alias_stato")
        ),
        sa.CheckConstraint(
            "confidenza >= 0 AND confidenza <= 1", name=op.f("ck_product_alias_confidenza")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_product_alias_product_id_product"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_product_alias_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_alias")),
    )
    op.create_index(
        "uq_product_alias_user_id_catena_testo_grezzo",
        "product_alias",
        ["user_id", "catena", "testo_grezzo"],
        unique=True,
        postgresql_where=sa.text("stato <> 'rifiutato'"),
    )
    op.create_table(
        "group_alternative",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("group_a", sa.UUID(), nullable=False),
        sa.Column("group_b", sa.UUID(), nullable=False),
        sa.Column("fonte", sa.Text(), nullable=False),
        sa.Column("fonte_id", sa.UUID(), nullable=True),
        sa.Column(
            "acquisito_il",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confidenza", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("stato", sa.Text(), server_default=sa.text("'auto'"), nullable=False),
        sa.CheckConstraint(
            "fonte IN ('volantino', 'scontrino', 'umano', 'regola')",
            name=op.f("ck_group_alternative_fonte"),
        ),
        sa.CheckConstraint(
            "stato IN ('auto', 'rivisto', 'rifiutato')", name=op.f("ck_group_alternative_stato")
        ),
        sa.CheckConstraint(
            "confidenza >= 0 AND confidenza <= 1", name=op.f("ck_group_alternative_confidenza")
        ),
        sa.CheckConstraint("group_a <> group_b", name=op.f("ck_group_alternative_gruppi_diversi")),
        sa.ForeignKeyConstraint(
            ["group_a"],
            ["product_group.id"],
            name=op.f("fk_group_alternative_group_a_product_group"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_b"],
            ["product_group.id"],
            name=op.f("fk_group_alternative_group_b_product_group"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_group_alternative_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_group_alternative")),
        sa.UniqueConstraint(
            "user_id", "group_a", "group_b", name=op.f("uq_group_alternative_user_id")
        ),
    )

    op.create_table(
        "flyer",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("catena", sa.Text(), nullable=False),
        sa.Column("insegna", sa.Text(), nullable=True),
        sa.Column("zona", sa.Text(), nullable=True),
        sa.Column("validita_da", sa.Date(), nullable=False),
        sa.Column("validita_a", sa.Date(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("numero_pagine", sa.Integer(), nullable=True),
        sa.Column("url_origine", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("incluso", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "catena IN ('lidl', 'eurospin', 'coop', 'altra')", name=op.f("ck_flyer_catena")
        ),
        sa.CheckConstraint("tipo IN ('settimanale', 'catalogo')", name=op.f("ck_flyer_tipo")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_flyer_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flyer")),
        sa.UniqueConstraint("user_id", "sha256", name=op.f("uq_flyer_user_id")),
    )
    op.create_table(
        "offer",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("flyer_id", sa.UUID(), nullable=False),
        sa.Column("pagina", sa.Integer(), nullable=True),
        sa.Column("testo_grezzo", sa.Text(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("prezzo_confezione", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("prezzo_unitario", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("unita", sa.Text(), nullable=True),
        sa.Column("prezzo_barrato", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("sconto_dichiarato", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("validita_da", sa.Date(), nullable=True),
        sa.Column("validita_a", sa.Date(), nullable=True),
        sa.Column("condizione", sa.Text(), server_default=sa.text("'nessuna'"), nullable=False),
        sa.Column("quantita_minima", sa.Integer(), nullable=True),
        sa.Column("limite_pezzi", sa.Integer(), nullable=True),
        sa.Column("fonte", sa.Text(), nullable=False),
        sa.Column("fonte_id", sa.UUID(), nullable=True),
        sa.Column(
            "acquisito_il",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confidenza", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("stato", sa.Text(), server_default=sa.text("'auto'"), nullable=False),
        sa.CheckConstraint(
            "condizione IN ('nessuna', 'carta_fedelta', 'multi_acquisto')",
            name=op.f("ck_offer_condizione"),
        ),
        sa.CheckConstraint("unita IN ('kg', 'L', 'pezzo')", name=op.f("ck_offer_unita")),
        sa.CheckConstraint(
            "fonte IN ('volantino', 'scontrino', 'umano', 'regola')",
            name=op.f("ck_offer_fonte"),
        ),
        sa.CheckConstraint(
            "stato IN ('auto', 'rivisto', 'rifiutato')", name=op.f("ck_offer_stato")
        ),
        sa.CheckConstraint("confidenza >= 0 AND confidenza <= 1", name=op.f("ck_offer_confidenza")),
        sa.ForeignKeyConstraint(
            ["flyer_id"],
            ["flyer.id"],
            name=op.f("fk_offer_flyer_id_flyer"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_offer_product_id_product"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_offer_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_offer")),
    )
    op.create_table(
        "receipt",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("data_ora", sa.DateTime(), nullable=False),
        sa.Column("catena", sa.Text(), nullable=False),
        sa.Column("totale", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("impronta", sa.Text(), nullable=True),
        sa.Column("estrazione_grezza", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "catena IN ('lidl', 'eurospin', 'coop', 'altra')", name=op.f("ck_receipt_catena")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_receipt_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_receipt")),
        sa.UniqueConstraint(
            "user_id", "catena", "data_ora", "totale", name=op.f("uq_receipt_user_id")
        ),
    )
    op.create_table(
        "receipt_line",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("receipt_id", sa.UUID(), nullable=False),
        sa.Column("testo_grezzo", sa.Text(), nullable=False),
        sa.Column("quantita", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("prezzo", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "sconto", sa.Numeric(precision=10, scale=2), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("fonte", sa.Text(), nullable=False),
        sa.Column("fonte_id", sa.UUID(), nullable=True),
        sa.Column(
            "acquisito_il",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("confidenza", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("stato", sa.Text(), server_default=sa.text("'auto'"), nullable=False),
        sa.CheckConstraint(
            "fonte IN ('volantino', 'scontrino', 'umano', 'regola')",
            name=op.f("ck_receipt_line_fonte"),
        ),
        sa.CheckConstraint(
            "stato IN ('auto', 'rivisto', 'rifiutato')", name=op.f("ck_receipt_line_stato")
        ),
        sa.CheckConstraint(
            "confidenza >= 0 AND confidenza <= 1", name=op.f("ck_receipt_line_confidenza")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_receipt_line_product_id_product"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipt.id"],
            name=op.f("fk_receipt_line_receipt_id_receipt"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_receipt_line_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_receipt_line")),
    )

    op.create_table(
        "inventory_item",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("data_ultimo_acquisto", sa.Date(), nullable=True),
        sa.Column("quantita_ultimo_acquisto", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("tasso_consumo", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("durata_stimata_giorni", sa.Integer(), nullable=True),
        sa.Column("scadenza_reale", sa.Date(), nullable=True),
        sa.Column(
            "probabilmente_finito", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("livello", sa.SmallInteger(), nullable=False),
        sa.Column("livello_confidenza", sa.Text(), nullable=False),
        sa.CheckConstraint("livello IN (0, 1, 2)", name=op.f("ck_inventory_item_livello")),
        sa.CheckConstraint(
            "livello_confidenza IN ('bassa', 'media', 'alta')",
            name=op.f("ck_inventory_item_livello_confidenza"),
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["product_group.id"],
            name=op.f("fk_inventory_item_group_id_product_group"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_inventory_item_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_item")),
        sa.UniqueConstraint("user_id", "group_id", name=op.f("uq_inventory_item_user_id")),
    )
    op.create_table(
        "job",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("stato", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("tentativi", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("lease_scade_il", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "stato IN ('pending', 'running', 'done', 'failed')", name=op.f("ck_job_stato")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_job_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job")),
    )

    for tabella in TABELLE:
        op.execute(f"ALTER TABLE {tabella} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Ordine inverso: i figli prima dei genitori. La RLS sparisce con le tabelle.
    for tabella in reversed(TABELLE):
        op.drop_table(tabella)
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
