"""auth and settings tables

Pasa auth y settings a las capas nuevas:
- users: role manager | salesperson, salesperson_code (antes sales_rep_code), full_name y phone.
- Crea pricing_settings, customer_levels y level_thresholds.
- Quita las tablas del esqueleto plano: customer_tiers, customer_rebates, quotes y quote_lines.

users y contacts se recrean en vez de alterarse (en SQLite cambiar una FK obliga a recrear la tabla). Es seguro
porque ninguna base tiene usuarios ni contactos todavía; si las tablas tienen filas, la migración se detiene.

Revision ID: bc3d285b5ffb
Revises: e811b35b030d
Create Date: 2026-10-13 21:17:43.100788
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'bc3d285b5ffb'
down_revision: str | None = 'e811b35b030d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _require_empty(*tables: str) -> None:
    bind = op.get_bind()
    for table in tables:
        if bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError(f"La tabla {table} tiene filas: esta migración la recrea y se perderían. Migrar a mano.")


def _create_users(new_shape: bool) -> None:
    columns = [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=300), nullable=False),
    ]
    if new_shape:
        columns += [
            sa.Column("full_name", sa.String(length=150), nullable=False),
            sa.Column("phone", sa.String(length=40), nullable=True),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("salesperson_code", sa.String(length=3), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(["salesperson_code"], ["salespeople.code"], name="users_salesperson_code_fkey"),
        ]
    else:
        columns += [
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("sales_rep_code", sa.String(length=3), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(["sales_rep_code"], ["salespeople.code"], name="users_sales_rep_code_fkey"),
        ]
    op.create_table("users", *columns, sa.PrimaryKeyConstraint("id", name="users_pkey"))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)


def _create_contacts() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ruc", sa.String(length=15), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("contact_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["ruc"], ["customers.ruc"], name="contacts_ruc_fkey"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="contacts_user_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="contacts_pkey"),
    )
    op.create_index(op.f("ix_contacts_ruc"), "contacts", ["ruc"], unique=False)


def _drop_users_and_contacts() -> None:
    op.drop_index(op.f("ix_contacts_ruc"), table_name="contacts")
    op.drop_table("contacts")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")


def upgrade() -> None:
    _require_empty("users", "contacts")
    op.drop_index(op.f("ix_quotes_ruc"), table_name="quotes")
    op.drop_table("quote_lines")
    op.drop_table("quotes")
    op.drop_table("customer_rebates")
    op.drop_table("customer_tiers")
    _drop_users_and_contacts()
    _create_users(new_shape=True)
    _create_contacts()
    op.create_table(
        "pricing_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("igv_rate_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("quotation_validity_days", sa.Integer(), nullable=False),
        sa.Column("min_margin_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("promo_margin_cut_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pricing_settings_pkey"),
    )
    op.create_table(
        "customer_levels",
        sa.Column("level", sa.String(length=1), nullable=False),
        sa.Column("max_discount_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("margin_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("credit_days", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("level", name="customer_levels_pkey"),
    )
    op.create_table(
        "level_thresholds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("min_amount_b", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("min_amount_a", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id", name="level_thresholds_pkey"),
    )


def downgrade() -> None:
    _require_empty("users", "contacts")
    op.drop_table("level_thresholds")
    op.drop_table("customer_levels")
    op.drop_table("pricing_settings")
    _drop_users_and_contacts()
    _create_users(new_shape=False)
    _create_contacts()
    op.create_table(
        "customer_tiers",
        sa.Column("tier", sa.String(length=1), nullable=False),
        sa.Column("max_discount_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("margin_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("credit_days", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("tier", name="customer_tiers_pkey"),
    )
    op.create_table(
        "customer_rebates",
        sa.Column("ruc", sa.String(length=15), nullable=False),
        sa.Column("rebate_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["ruc"], ["customers.ruc"], name="customer_rebates_ruc_fkey"),
        sa.PrimaryKeyConstraint("ruc", name="customer_rebates_pkey"),
    )
    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ruc", sa.String(length=15), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("discount_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ruc"], ["customers.ruc"], name="quotes_ruc_fkey"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="quotes_user_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="quotes_pkey"),
    )
    op.create_index(op.f("ix_quotes_ruc"), "quotes", ["ruc"], unique=False)
    op.create_table(
        "quote_lines",
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["product_code"], ["products.code"], name="quote_lines_product_code_fkey"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], name="quote_lines_quote_id_fkey"),
        sa.PrimaryKeyConstraint("quote_id", "product_code", name="quote_lines_pkey"),
    )
