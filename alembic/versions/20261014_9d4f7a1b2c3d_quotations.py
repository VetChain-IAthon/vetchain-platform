"""Tablas de cotizaciones emitidas.

Revision ID: 9d4f7a1b2c3d
Revises: bc3d285b5ffb
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "9d4f7a1b2c3d"
down_revision: str | None = "bc3d285b5ffb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ruc", sa.String(15), sa.ForeignKey("customers.ruc"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("discount_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("net", sa.Numeric(14, 2), nullable=False),
        sa.Column("igv", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_with_tax", sa.Numeric(14, 2), nullable=False),
        sa.Column("margin_pct", sa.Numeric(7, 2)),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("approval_reasons", sa.Text(), nullable=False),
        sa.Column("approval_confirmed", sa.Boolean(), nullable=False),
        sa.Column("approval_note", sa.Text()),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("order_no", sa.String(20)),
    )
    op.create_index("ix_quotations_ruc", "quotations", ["ruc"])
    op.create_index("ix_quotations_issued_on", "quotations", ["issued_on"])
    op.create_table(
        "quotation_lines",
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("quotations.id"), primary_key=True),
        sa.Column("product_code", sa.String(20), sa.ForeignKey("products.code"), primary_key=True),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("price_origin", sa.String(20), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2)),
    )


def downgrade() -> None:
    op.drop_table("quotation_lines")
    op.drop_index("ix_quotations_issued_on", table_name="quotations")
    op.drop_index("ix_quotations_ruc", table_name="quotations")
    op.drop_table("quotations")
