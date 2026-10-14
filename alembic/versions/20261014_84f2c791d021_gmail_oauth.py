"""Conexiones Gmail OAuth individuales.

Revision ID: 84f2c791d021
Revises: 3b8d5e2f9a71
"""
from alembic import op
import sqlalchemy as sa

revision = "84f2c791d021"
down_revision = "3b8d5e2f9a71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_connections",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
    )
    op.create_table(
        "gmail_oauth_attempts",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("return_path", sa.String(500), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gmail_oauth_attempts")
    op.drop_table("gmail_connections")
