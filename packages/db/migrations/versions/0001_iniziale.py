"""iniziale: User ed Exclusion, estensione pg_trgm, RLS senza policy

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
TABELLE = ["app_user", "exclusion"]


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

    for tabella in TABELLE:
        op.execute(f"ALTER TABLE {tabella} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Ordine inverso: i figli prima dei genitori. La RLS sparisce con le tabelle.
    for tabella in reversed(TABELLE):
        op.drop_table(tabella)
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
