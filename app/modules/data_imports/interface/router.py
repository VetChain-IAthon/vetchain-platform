from fastapi import APIRouter

from app.core.application import MANAGER, SALESPERSON
from app.core.stubs import add_pending_route

router = APIRouter(tags=["carga de datos"])
M, MS = (MANAGER,), (MANAGER, SALESPERSON)

# Rutas del contrato (docs/endpoints.md). Se reemplazan por rutas reales al construir el módulo.
for method, path, roles, summary in [
    ("GET", "/data-sources", M, "Los 7 archivos: contenido, registros, período y estado"),
    ("POST", "/data-imports", M, "Subir un CSV (multipart, campo source); se valida pero no se aplica"),
    ("GET", "/data-imports", M, "Cargas anteriores"),
    ("GET", "/data-imports/{import_id}", M, "Revisión: filas leídas y errores por línea"),
    ("PATCH", "/data-imports/{import_id}", M, "Confirmar (actualiza e inserta) o cancelar"),
]:
    add_pending_route(router, method, path, roles, summary)
