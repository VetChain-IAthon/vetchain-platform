from fastapi import APIRouter

from app.core.application import MANAGER, SALESPERSON
from app.core.stubs import add_pending_route

router = APIRouter(tags=["panel y reportes"])
M, MS = (MANAGER,), (MANAGER, SALESPERSON)

# Rutas del contrato (docs/endpoints.md). Se reemplazan por rutas reales al construir el módulo.
for method, path, roles, summary in [
    ("GET", "/dashboard/summary", M, "Resumen semanal y cifras principales"),
    ("GET", "/reports", M, "Catálogo de reportes con el origen de sus datos"),
    ("GET", "/reports/kpis", M, "Los KPIs con su estado"),
    ("GET", "/reports/sales", M, "Pedidos por mes, producto y categoría"),
    ("GET", "/reports/customers", M, "Concentración, maestro de clientes, en riesgo y dormidos"),
    ("GET", "/reports/stock", M, "Estado del stock"),
    ("GET", "/reports/receivables", M, "Deuda por antigüedad y nivel (estimada)"),
    ("GET", "/reports/salespeople", M, "Pedidos de 12 meses y seguimiento de alertas por vendedor"),
    ("GET", "/reports/funnel", M, "Embudo: alertas, contactos, cotizaciones, convertidas y monto recuperado"),
]:
    add_pending_route(router, method, path, roles, summary)
