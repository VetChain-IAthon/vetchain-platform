from fastapi import APIRouter

from app.core.application import MANAGER, SALESPERSON
from app.core.stubs import add_pending_route

router = APIRouter(tags=["clientes y alertas"])
M, MS = (MANAGER,), (MANAGER, SALESPERSON)

# Rutas del contrato (docs/endpoints.md). Se reemplazan por rutas reales al construir el módulo.
for method, path, roles, summary in [
    ("GET", "/alerts", MS, "Alertas del día, ordenadas por dinero en juego"),
    ("GET", "/alerts/summary", MS, "Totales: alertas, contactados hoy, monto de 12 meses en juego"),
    ("GET", "/alerts/{alert_id}", MS, "Una alerta: producto habitual, producto cruzado, motivos y probabilidad"),
    ("GET", "/alerts/{alert_id}/explanation", MS, "Texto de IA que explica la alerta (solo cifras agregadas)"),
    ("GET", "/customers", MS, "Lista de clientes con filtros de nivel, estado, búsqueda y vendedor"),
    ("GET", "/customers/{ruc}", MS, "Ficha del cliente con nivel y resumen de 12 meses"),
    ("GET", "/customers/{ruc}/orders", MS, "Historial de pedidos"),
    ("GET", "/customers/{ruc}/products", MS, "Qué compra el cliente y con qué frecuencia"),
    ("GET", "/customers/{ruc}/commercial-terms", MS, "Nivel, margen, descuento máximo y días de crédito"),
    ("GET", "/customers/{ruc}/contacts", MS, "Registro de contactos"),
    ("POST", "/customers/{ruc}/contacts", MS, "Registrar un contacto y su resultado"),
    ("GET", "/customers/{ruc}/whatsapp-link", MS, "Enlace wa.me con el mensaje sugerido"),
    ("GET", "/customers/{ruc}/brief", M, "Ficha del cliente para reunión (from, to, projection)"),
]:
    add_pending_route(router, method, path, roles, summary)
