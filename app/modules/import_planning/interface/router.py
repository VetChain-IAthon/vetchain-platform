from fastapi import APIRouter

from app.core.application import MANAGER, SALESPERSON
from app.core.stubs import add_pending_route

router = APIRouter(tags=["planificación de importación"])
M, MS = (MANAGER,), (MANAGER, SALESPERSON)

# Rutas del contrato (docs/endpoints.md). Se reemplazan por rutas reales al construir el módulo.
for method, path, roles, summary in [
    ("GET", "/import-suggestions", M, "Pedido sugerido por producto"),
    ("PATCH", "/import-suggestions/{suggestion_id}", M, "Decisión: aprobar, rechazar o volver a pendiente"),
]:
    add_pending_route(router, method, path, roles, summary)
