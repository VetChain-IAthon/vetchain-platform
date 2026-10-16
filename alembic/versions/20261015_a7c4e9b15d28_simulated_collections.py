"""Cobranza simulada por cliente para la pantalla Hoy (perfiles de pago de ejemplo).

La interfaz asigna un perfil a cada cliente según su RUC (siempre el mismo) y lo marca «Simulado».

Revision ID: a7c4e9b15d28
Revises: f1a8d3c62b47
"""
from alembic import op
import sqlalchemy as sa

revision = "a7c4e9b15d28"
down_revision = "f1a8d3c62b47"
branch_labels = None
depends_on = None

COLLECTIONS = {
    # weight: cuántos de cada 10 clientes; {amount} en soles y {days} en días, dentro de los rangos.
    "profiles": [
        {"status": "Al día", "tone": "ok", "detail": "Paga en {days} días en promedio", "amount": [0, 0], "days": [12, 28], "weight": 5},
        {"status": "Por vencer", "tone": "warn", "detail": "S/ {amount} vence en {days} días", "amount": [900, 6500], "days": [3, 12], "weight": 3},
        {"status": "Vencida", "tone": "danger", "detail": "S/ {amount} con {days} días de atraso", "amount": [1200, 9800], "days": [8, 75], "weight": 2},
    ],
}


def upgrade() -> None:
    table = sa.table("simulated_sections", sa.column("key", sa.String), sa.column("payload", sa.JSON), sa.column("origin", sa.String))
    op.bulk_insert(table, [{"key": "collections", "payload": COLLECTIONS, "origin": "simulated"}])


def downgrade() -> None:
    op.execute("DELETE FROM simulated_sections WHERE key = 'collections'")
