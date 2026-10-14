from fastapi import APIRouter

from app.core.application import MANAGER, SALESPERSON
from app.core.stubs import add_pending_route

router = APIRouter(tags=["predicción"])
M, MS = (MANAGER,), (MANAGER, SALESPERSON)

# Rutas del contrato (docs/endpoints.md). Se reemplazan por rutas reales al construir el módulo.
for method, path, roles, summary in [
    ("GET", "/prediction/model", M, "Versión, fecha de entrenamiento y calidad del modelo"),
]:
    add_pending_route(router, method, path, roles, summary)
