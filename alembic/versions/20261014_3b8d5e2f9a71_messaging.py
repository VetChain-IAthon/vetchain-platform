"""Remitentes de correo permitidos y registro de envíos.

Revision ID: 3b8d5e2f9a71
Revises: 7e2a9c4d1f60
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "3b8d5e2f9a71"
down_revision: str | None = "7e2a9c4d1f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_senders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address", sa.String(200), nullable=False, unique=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("from_email", sa.String(200), nullable=False),
        sa.Column("recipients", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attachment_names", sa.Text(), nullable=False),
        sa.Column("provider_message_id", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_logs_user_id", "email_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_email_logs_user_id", table_name="email_logs")
    op.drop_table("email_logs")
    op.drop_table("email_senders")
