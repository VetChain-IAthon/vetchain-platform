from fastapi import APIRouter

from app.core.application import MANAGER, SALESPERSON
from app.core.stubs import add_pending_route

router = APIRouter(tags=["cotizaciones"])
M, MS = (MANAGER,), (MANAGER, SALESPERSON)

# Rutas del contrato (docs/endpoints.md). Se reemplazan por rutas reales al construir el módulo.
for method, path, roles, summary in [
    ("GET", "/products", MS, "Buscar productos para cotizar"),
    ("GET", "/products/{code}", MS, "Un producto con su precio de referencia"),
    ("POST", "/quotation-previews", MS, "Calcular totales, IGV y margen sin guardar"),
    ("GET", "/quotations", MS, "Lista de cotizaciones con filtros"),
    ("POST", "/quotations", MS, "Emitir una cotización (valida descuento y margen)"),
    ("GET", "/quotations/{quotation_id}", MS, "Detalle de una cotización con sus líneas"),
]:
    add_pending_route(router, method, path, roles, summary)
