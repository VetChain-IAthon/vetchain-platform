"""Más productos de demostración en la planificación de importación (5 por laboratorio, todos is_demo).

Revision ID: e4b7c2a91f30
Revises: 5a1c7e3d9b20
"""
from alembic import op
import sqlalchemy as sa

revision = "e4b7c2a91f30"
down_revision = "5a1c7e3d9b20"
branch_labels = None
depends_on = None

FIRST_ID = 13
ROWS = [  # laboratorio, producto, stock, cobertura, demanda 90 días, pedido sugerido, vida útil (meses), días para pedir, US$ unidad
    (1, "Desparasitante felino 4 comp", 520, 19, 2450, 2100, 18, 3, 6),
    (1, "Meloxicam oral 32 ml", 690, 33, 1880, 1300, 15, 12, 14),
    (1, "Shampoo dermatológico 200 ml", 410, 47, 790, 420, 20, 30, 9),
    (1, "Vacuna antirrábica 1 dosis", 1500, 58, 2320, 900, 10, 38, 3),
    (1, "Suplemento articular 60 tab", 260, 21, 1100, 950, 24, 4, 22),
    (2, "Pipeta antipulgas perro mediano", 980, 27, 3260, 2600, 30, 6, 7),
    (2, "Otológico limpiador 120 ml", 350, 44, 720, 400, 18, 25, 11),
    (2, "Probiótico canino 30 sobres", 300, 18, 1500, 1350, 12, 2, 16),
    (2, "Cicatrizante en spray 100 ml", 560, 61, 830, 300, 24, 42, 13),
    (2, "Alimento renal felino 2 kg", 140, 23, 540, 480, 9, 5, 28),
    (3, "Antiinflamatorio inyectable 50 ml", 230, 26, 790, 650, 14, 7, 35),
    (3, "Test parvovirus canino", 410, 35, 1050, 760, 10, 16, 19),
    (3, "Anestésico local 20 ml", 160, 31, 460, 330, 12, 13, 41),
    (3, "Hormonal reproductivo 10 ml", 95, 48, 180, 90, 8, 27, 58),
    (3, "Antimicótico tópico 30 g", 620, 66, 850, 280, 22, 46, 10),
    (4, "Electrolitos orales 1 kg", 1100, 29, 3400, 2700, 18, 9, 4),
    (4, "Vitamina B12 inyectable 50 ml", 480, 38, 1140, 760, 16, 18, 9),
    (4, "Larvicida para granjas 1 L", 300, 24, 1120, 950, 24, 6, 15),
    (4, "Desinfectante de ubres 5 L", 210, 53, 360, 180, 18, 33, 21),
    (4, "Premezcla mineral aves 25 kg", 90, 20, 400, 360, 12, 3, 64),
]


def upgrade() -> None:
    suggestions = sa.table(
        "import_suggestions",
        sa.column("id", sa.Integer), sa.column("laboratory_id", sa.Integer), sa.column("product_name", sa.String),
        sa.column("stock_units", sa.Integer), sa.column("coverage_days", sa.Integer), sa.column("demand_90_days", sa.Integer),
        sa.column("suggested_units", sa.Integer), sa.column("shelf_life_months", sa.Integer),
        sa.column("days_until_order", sa.Integer), sa.column("unit_price_usd", sa.Numeric(12, 2)),
        sa.column("decision", sa.String), sa.column("is_demo", sa.Boolean),
    )
    op.bulk_insert(suggestions, [dict(id=FIRST_ID + i, laboratory_id=lab, product_name=name, stock_units=stock,
        coverage_days=coverage, demand_90_days=demand, suggested_units=quantity, shelf_life_months=shelf,
        days_until_order=order, unit_price_usd=price, decision="pending", is_demo=True)
        for i, (lab, name, stock, coverage, demand, quantity, shelf, order, price) in enumerate(ROWS)])
    if op.get_context().dialect.name == "postgresql":
        op.execute("SELECT setval(pg_get_serial_sequence('import_suggestions', 'id'), "
                   "(SELECT MAX(id) FROM import_suggestions), true)")


def downgrade() -> None:
    op.execute(f"DELETE FROM import_suggestions WHERE is_demo AND id BETWEEN {FIRST_ID} AND {FIRST_ID + len(ROWS) - 1}")
