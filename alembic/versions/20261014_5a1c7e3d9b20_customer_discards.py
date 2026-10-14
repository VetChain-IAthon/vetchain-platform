"""Clientes dormidos descartados (cerraron, cambiaron de datos o ya no son viables).

Revision ID: 5a1c7e3d9b20
Revises: c9a25f4e108b
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "5a1c7e3d9b20"
down_revision: str | None = "c9a25f4e108b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_discards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ruc", sa.String(length=15), sa.ForeignKey("customers.ruc"), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("discarded_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("discarded_on", sa.Date(), nullable=False),
        sa.Column("restored_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("restored_on", sa.Date(), nullable=True),
    )
    op.create_index("ix_customer_discards_ruc", "customer_discards", ["ruc"])


def downgrade() -> None:
    op.drop_index("ix_customer_discards_ruc", table_name="customer_discards")
    op.drop_table("customer_discards")
