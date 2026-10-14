"""Tabla de cargas de CSV desde Ajustes.

Revision ID: 7e2a9c4d1f60
Revises: 9d4f7a1b2c3d
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "7e2a9c4d1f60"
down_revision: str | None = "9d4f7a1b2c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("file_name", sa.String(200), nullable=False),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("rows_with_error", sa.Integer(), nullable=False),
        sa.Column("rows_loaded", sa.Integer()),
        sa.Column("errors", sa.Text(), nullable=False),
        sa.Column("staged_rows", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_data_imports_source", "data_imports", ["source"])


def downgrade() -> None:
    op.drop_index("ix_data_imports_source", table_name="data_imports")
    op.drop_table("data_imports")
