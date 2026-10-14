"""Escenario de demostración para cuatro laboratorios.

Revision ID: c9a25f4e108b
Revises: 84f2c791d021
"""
from alembic import op
import sqlalchemy as sa

revision = "c9a25f4e108b"
down_revision = "84f2c791d021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    labs = op.create_table(
        "import_laboratories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("country", sa.String(80), nullable=False),
        sa.Column("lead_days", sa.Integer(), nullable=False),
        sa.Column("import_cost_usd", sa.Integer(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
    )
    suggestions = op.create_table(
        "import_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("laboratory_id", sa.Integer(), sa.ForeignKey("import_laboratories.id"), nullable=False),
        sa.Column("product_name", sa.String(150), nullable=False),
        sa.Column("stock_units", sa.Integer(), nullable=False),
        sa.Column("coverage_days", sa.Integer(), nullable=False),
        sa.Column("demand_90_days", sa.Integer(), nullable=False),
        sa.Column("suggested_units", sa.Integer(), nullable=False),
        sa.Column("shelf_life_months", sa.Integer(), nullable=False),
        sa.Column("days_until_order", sa.Integer(), nullable=False),
        sa.Column("unit_price_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_import_suggestions_laboratory_id", "import_suggestions", ["laboratory_id"])
    op.bulk_insert(labs, [
        {"id": 1, "name": "Laboratorio Nivalux", "country": "Brasil", "lead_days": 60, "import_cost_usd": 21400, "is_demo": True},
        {"id": 2, "name": "Laboratorio Ventoria", "country": "España", "lead_days": 75, "import_cost_usd": 14800, "is_demo": True},
        {"id": 3, "name": "Laboratorio Celumera", "country": "EE. UU.", "lead_days": 50, "import_cost_usd": 18700, "is_demo": True},
        {"id": 4, "name": "Laboratorio Zoravix", "country": "México", "lead_days": 45, "import_cost_usd": 9300, "is_demo": True},
    ])
    rows = [
        (1, "Antiparasitario oral 10 kg", 1240, 24, 4700, 3800, 9, 2, 20),
        (1, "Vacuna polivalente canina", 860, 41, 2300, 1600, 5, 19, 40),
        (1, "Antibiótico inyectable 100 ml", 2050, 63, 2900, 600, 11, 41, 70),
        (2, "Suplemento nutricional 1 kg", 720, 28, 2100, 1600, 12, 8, 18),
        (2, "Desinfectante veterinario 5 L", 430, 36, 1100, 850, 18, 14, 32),
        (2, "Jeringa veterinaria 20 ml", 2400, 52, 4200, 1900, 24, 34, 5),
        (3, "Analgesico veterinario 50 ml", 310, 22, 1250, 1100, 10, 1, 45),
        (3, "Prueba rapida canina", 640, 39, 1500, 1200, 8, 20, 27),
        (3, "Solucion oftalmica 15 ml", 880, 56, 1400, 700, 14, 39, 22),
        (4, "Champu antiseptico 250 ml", 560, 25, 1800, 1500, 16, 5, 12),
        (4, "Collar antiparasitario", 930, 43, 1950, 1200, 20, 22, 16),
        (4, "Vitaminas para aves 100 ml", 1400, 62, 2100, 800, 13, 44, 8),
    ]
    op.bulk_insert(suggestions, [dict(id=i, laboratory_id=lab, product_name=name, stock_units=stock,
        coverage_days=coverage, demand_90_days=demand, suggested_units=quantity, shelf_life_months=shelf,
        days_until_order=order, unit_price_usd=price, decision="pending", is_demo=True)
        for i, (lab, name, stock, coverage, demand, quantity, shelf, order, price) in enumerate(rows, 1)])
    if op.get_context().dialect.name == "postgresql":
        op.execute("SELECT setval(pg_get_serial_sequence('import_laboratories', 'id'), 4, true)")
        op.execute("SELECT setval(pg_get_serial_sequence('import_suggestions', 'id'), 12, true)")


def downgrade() -> None:
    op.drop_index("ix_import_suggestions_laboratory_id", table_name="import_suggestions")
    op.drop_table("import_suggestions")
    op.drop_table("import_laboratories")
