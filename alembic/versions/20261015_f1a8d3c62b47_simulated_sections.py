"""Secciones simuladas para la demostración (costos, lotes, facturas, alertas y proyección).

Revision ID: f1a8d3c62b47
Revises: e4b7c2a91f30
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a8d3c62b47"
down_revision = "e4b7c2a91f30"
branch_labels = None
depends_on = None


def _bars(*items):
    return {"type": "bars", "items": [{"label": label, "value": value, "note": note} for label, value, note in items]}


SECTIONS = {
    # Tarjetas de cifra (PendingTile), por etiqueta o clave. format: pen | pct | days | int | text
    "tiles": {
        "Indicadores en meta": {"value": "7 de 12", "format": "text", "detail": "3 en atención · 2 críticos"},
        "Por vencer en 90 días": {"value": 48320, "format": "pen", "detail": "14 lotes de 9 productos"},
        "Alertas atendidas en 48 horas": {"value": 82, "format": "pct", "detail": "164 de 200 alertas del período"},
        "Cotizaciones que terminan en pedido": {"value": 36, "format": "pct", "detail": "58 de 161 cotizaciones"},
        "Venta recuperada con alertas": {"value": 126480, "format": "pen", "detail": "41 clientes volvieron a pedir"},
        "Valor del stock": {"value": 1284650, "format": "pen", "detail": "Al costo de compra"},
        "Vence en 90 días": {"value": 48320, "format": "pen", "detail": "14 lotes · 9 productos"},
        "Merma 12 meses": {"value": 21940, "format": "pen", "detail": "1.1 % de la venta del período"},
        "Por cobrar": {"value": 412870, "format": "pen", "detail": "286 facturas abiertas"},
        "Vencida": {"value": 96540, "format": "pen", "detail": "23.4 % de lo por cobrar"},
        "Días promedio de cobro": {"value": 38, "format": "days", "detail": "Meta propuesta: 30 días"},
        "Facturas pagadas a tiempo": {"value": 71, "format": "pct", "detail": "Meta propuesta: 80 %"},
        "Ganancia estimada": {"value": 590710, "format": "pen", "detail": "Margen de 29.0 % sobre la venta"},
        "Proyección en soles": {"value": 556300, "format": "pen", "detail": "Abril a junio de 2026, sin IGV"},
        "ficha-ganancia": {"value": 14860, "format": "pen", "detail": "Margen de 27.5 % en sus compras"},
        "ficha-proyeccion": {"value": 18400, "format": "pen", "detail": "Según su ritmo de compra"},
        "ficha-propuesta": {"value": 6850, "format": "pen", "detail": "3 productos con lote por vencer"},
    },
    # Secciones completas (Pending), por título.
    "sections": {
        "Envíos programados": {"type": "table", "head": ["Reporte", "Frecuencia", "Destinatarios", "Próximo envío"], "rows": [
            ["Panel gerencial", "Lunes 8:00", "Gerencia (3)", "19 oct. 2026"],
            ["Ventas y rentabilidad", "Día 1 de cada mes", "Gerencia y finanzas (4)", "01 nov. 2026"],
            ["Cartera y cobranza", "Lunes y jueves 9:00", "Cobranzas (2)", "19 oct. 2026"],
            ["Stock y merma", "Viernes 17:00", "Compras (2)", "16 oct. 2026"]]},
        "Valor que vence, por plazo": _bars(("30 días", 12400, None), ("60 días", 18900, None), ("90 días", 17020, None),
                                            ("120 días", 22300, None), ("180 días", 31800, None)),
        "Lotes por vencer y a quién ofrecerlos": {"type": "table",
            "head": ["Producto", "Lote", "Vence", "Unidades", "Ofrecer a", "Acción sugerida"], "rows": [
                ["Antiparasitario oral 10 kg", "L-2407", "12 dic. 2026", "180", "Clínicas con pedido mensual (12)", "Sumarlo a su pedido habitual"],
                ["Vitaminas para aves 100 ml", "L-2311", "20 dic. 2026", "95", "Distribuidores avícolas (5)", "Promoción 2 × 1.8"],
                ["Antibiótico inyectable 100 ml", "L-2402", "08 ene. 2027", "140", "Veterinarias de provincia (9)", "Descuento por volumen 8 %"],
                ["Champú antiséptico 250 ml", "L-2405", "15 ene. 2027", "60", "Pet shops de Lima (7)", "Incluir en próxima visita"]]},
        "Venta por categoría": _bars(("Antiparasitarios", 631448, "31 %"), ("Antibióticos", 448125, "22 %"),
                                     ("Vitaminas y suplementos", 346278, "17 %"), ("Vacunas", 285170, "14 %"),
                                     ("Dermatológicos", 183324, "9 %"), ("Otros", 142586, "7 %")),
        "Ganancia estimada por nivel de cliente": _bars(("Nivel A", 268400, "margen 24 %"), ("Nivel B", 201300, "margen 30 %"),
                                                        ("Nivel C", 121010, "margen 34 %")),
        "Resumen para la reunión": {"type": "text", "text": "Cliente estable con compras mensuales y ticket por encima del "
            "promedio. En los últimos tres meses redujo la frecuencia de antiparasitarios; conviene recuperar ese pedido y "
            "proponer el lote de vitaminas por vencer con descuento por volumen."},
        "Qué ofrecerle": {"type": "table", "head": ["Producto", "Por qué", "Precio sugerido"], "rows": [
            ["Antiparasitario oral 10 kg", "Lo pedía cada mes y lleva 2 meses sin pedirlo", "S/ 42.50"],
            ["Vitaminas para aves 100 ml", "Lote por vencer; compra productos similares", "S/ 18.90"],
            ["Vacuna polivalente canina", "Temporada alta de vacunación", "S/ 36.00"]]},
        "Guion para la reunión": {"type": "list", "items": [
            "Agradecer la compra del último mes y confirmar si el stock le alcanzó.",
            "Preguntar por el antiparasitario: si cambió de proveedor o bajó su demanda.",
            "Ofrecer el lote de vitaminas con descuento por volumen.",
            "Cerrar con fecha del próximo pedido y recordar el estado de su crédito."]},
        "Crédito y cobranza": {"type": "stats", "items": [
            {"label": "Línea de crédito", "value": 30000, "format": "pen"},
            {"label": "Deuda vigente", "value": 8420, "format": "pen"},
            {"label": "Días promedio de pago", "value": 34, "format": "days"}]},
        "Nuestra propuesta": {"type": "text", "text": "Pedido sugerido de S/ 6,850.00 sin IGV: antiparasitario oral (24 u), "
            "vitaminas para aves (30 u) y vacuna polivalente (12 u), con descuento de 6 % por volumen y entrega en la próxima ruta."},
    },
    "receivables": {
        "aging": [41200, 27800, 14900, 12640],
        "levels": {"A": 50200.80, "B": 29927.40, "C": 16411.80},
        "debtors": [
            {"name": "Cliente de ejemplo 1", "level": "A", "amount": 18420, "days": 45, "invoices": 4, "action": "Llamar hoy y pausar nuevos créditos"},
            {"name": "Cliente de ejemplo 2", "level": "A", "amount": 12960, "days": 32, "invoices": 3, "action": "Acordar fecha de pago esta semana"},
            {"name": "Cliente de ejemplo 3", "level": "B", "amount": 9870, "days": 68, "invoices": 5, "action": "Pedir pago antes del próximo pedido"},
            {"name": "Cliente de ejemplo 4", "level": "B", "amount": 7340, "days": 21, "invoices": 2, "action": "Recordatorio por WhatsApp"},
            {"name": "Cliente de ejemplo 5", "level": "C", "amount": 5120, "days": 97, "invoices": 3, "action": "Solo pago al contado"},
        ],
    },
    "salespeople": {
        "funnel": [200, 164, 96, 58],
        "recovered": 126480,
        # Por posición en el ranking de venta: alertas, contactados en 48 h, cotizaciones, pedidos, venta recuperada (S/)
        "follow_up": [[64, 58, 35, 22, 47960], [48, 41, 25, 15, 32700], [37, 30, 18, 10, 21800],
                      [26, 20, 12, 6, 13080], [15, 11, 6, 3, 6540], [10, 4, 2, 2, 4400]],
    },
    # KPIs que esperan datos de Mederi (valor en %, salvo reactivated que es un conteo).
    "kpis": {"margin": 28.9, "waste": 1.1, "overdue": 23.4, "alerts": 82, "quotes": 36, "reactivated": 31},
    # Proyección mensual en soles para el gráfico de Ventas.
    "sales": {"projection": [{"month": "2026-04", "amount": 178400}, {"month": "2026-05", "amount": 185900},
                             {"month": "2026-06", "amount": 192000}]},
}


def upgrade() -> None:
    table = op.create_table(
        "simulated_sections",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False, server_default="simulated"),
    )
    op.bulk_insert(table, [{"key": key, "payload": payload, "origin": "simulated"} for key, payload in SECTIONS.items()])


def downgrade() -> None:
    op.drop_table("simulated_sections")
