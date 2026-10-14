from fastapi import APIRouter

from app.core.application import MANAGER, SALESPERSON
from app.core.stubs import add_pending_route

router = APIRouter(tags=["preguntas a los datos"])
M, MS = (MANAGER,), (MANAGER, SALESPERSON)

# Rutas del contrato (docs/endpoints.md). Se reemplazan por rutas reales al construir el módulo.
for method, path, roles, summary in [
    ("POST", "/insights/questions", M, "Pregunta en lenguaje natural; la respuesta lista sus fuentes"),
]:
    add_pending_route(router, method, path, roles, summary)
