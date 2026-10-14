from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.core.application import MANAGER, SALESPERSON, Paging, SessionUser
from app.core.auth import require_role
from app.core.stubs import add_pending_route
from app.modules.customers.application import use_cases as uc
from app.modules.customers.interface import dependencies as deps
from app.modules.customers.interface.schemas import (
    CommercialTermsOut,
    ContactIn,
    ContactOut,
    ContactPageOut,
    CustomerDetailOut,
    CustomerListItemOut,
    AtRiskCustomerPageOut,
    AtRiskFollowUpOut,
    CustomerPageOut,
    DormantCustomerPageOut,
    OrderOut,
    OrderPageOut,
    ProductPurchaseOut,
    ProductPurchasesOut,
    WhatsappLinkOut,
)

router = APIRouter(tags=["clientes y alertas"])
M, MS = (MANAGER,), (MANAGER, SALESPERSON)
any_role = require_role(*MS)

Page = Query(1, ge=1)
PerPage = Query(20, ge=1, le=100)


@router.get("/customers", response_model=CustomerPageOut)
def list_customers(
    search: str | None = Query(None, max_length=100, description="Nombre o inicio del RUC"),
    level: Literal["A", "B", "C"] | None = None,
    salesperson_code: str | None = Query(None, max_length=3, description="Solo gerencia; al vendedor se le fuerza el suyo"),
    page: int = Page,
    per_page: int = PerPage,
    user: SessionUser = Depends(any_role),
    use_case: uc.ListCustomers = Depends(deps.get_list_customers),
):
    """Cartera ordenada por monto de pedidos de 12 meses, con nivel y participación."""
    result = use_case.execute(uc.ListCustomersQuery(search, level, Paging(page, per_page)), uc.scope_for(user, salesperson_code))
    return CustomerPageOut(
        items=[CustomerListItemOut.from_result(item) for item in result.page.items],
        total=result.page.total, page=result.page.page, per_page=result.page.per_page,
        total_amount_12m=result.total_amount_12m.amount, data_as_of=result.data_as_of,
        levels_configured=result.levels_configured,
    )


@router.get("/customers/at-risk", response_model=AtRiskCustomerPageOut)
def list_at_risk_customers(
    salesperson_code: str | None = Query(None, max_length=3, description="Solo gerencia; al vendedor se le fuerza el suyo"),
    page: int = Page,
    per_page: int = PerPage,
    user: SessionUser = Depends(any_role),
    use_case: uc.ListAtRiskCustomers = Depends(deps.get_list_at_risk_customers),
):
    """Clientes que compran menos seguido de lo habitual, por dinero en juego. Factores provisionales (1,5× su ritmo)."""
    return AtRiskCustomerPageOut.from_result(use_case.execute(uc.scope_for(user, salesperson_code), Paging(page, per_page)))


@router.get("/customers/at-risk/follow-up", response_model=AtRiskFollowUpOut)
def get_at_risk_follow_up(
    salesperson_code: str | None = Query(None, max_length=3, description="Solo gerencia; al vendedor se le fuerza el suyo"),
    user: SessionUser = Depends(any_role),
    use_case: uc.GetAtRiskFollowUp = Depends(deps.get_at_risk_follow_up),
):
    """Por vendedor: clientes en riesgo y soles en juego según el resultado del último contacto (o sin contactar)."""
    return AtRiskFollowUpOut.from_result(use_case.execute(uc.scope_for(user, salesperson_code)))


@router.get("/customers/dormant", response_model=DormantCustomerPageOut)
def list_dormant_customers(
    search: str | None = Query(None, max_length=100, description="Nombre, departamento o inicio del RUC"),
    customer_type: Literal["company", "person"] | None = None,
    salesperson_code: str | None = Query(None, max_length=3, description="Solo gerencia; al vendedor se le fuerza el suyo"),
    page: int = Page,
    per_page: int = PerPage,
    user: SessionUser = Depends(any_role),
    use_case: uc.ListDormantCustomers = Depends(deps.get_list_dormant_customers),
):
    """Clientes sin pedidos en los últimos 12 meses (incluye a los que nunca pidieron), por monto histórico."""
    query = uc.DormantCustomersQuery(search, customer_type, Paging(page, per_page))
    return DormantCustomerPageOut.from_result(use_case.execute(query, uc.scope_for(user, salesperson_code)))


@router.get("/customers/{ruc}", response_model=CustomerDetailOut)
def get_customer(ruc: str, user: SessionUser = Depends(any_role), use_case: uc.GetCustomer = Depends(deps.get_get_customer)):
    """Ficha del cliente con nivel, resumen de 12 meses e historial completo."""
    return CustomerDetailOut.from_result(use_case.execute(ruc, uc.scope_for(user)))


@router.get("/customers/{ruc}/orders", response_model=OrderPageOut)
def list_customer_orders(
    ruc: str, page: int = Page, per_page: int = PerPage,
    user: SessionUser = Depends(any_role), use_case: uc.ListCustomerOrders = Depends(deps.get_list_customer_orders),
):
    """Historial de pedidos (todos los estados), del más reciente al más antiguo."""
    result = use_case.execute(ruc, uc.scope_for(user), Paging(page, per_page))
    return OrderPageOut(items=[OrderOut.from_domain(o) for o in result.items], total=result.total, page=result.page, per_page=result.per_page)


@router.get("/customers/{ruc}/products", response_model=ProductPurchasesOut)
def list_customer_products(
    ruc: str, user: SessionUser = Depends(any_role), use_case: uc.ListCustomerProducts = Depends(deps.get_list_customer_products)
):
    """Productos veterinarios que compra, de mayor a menor monto."""
    return ProductPurchasesOut(items=[ProductPurchaseOut.from_domain(p) for p in use_case.execute(ruc, uc.scope_for(user))])


@router.get("/customers/{ruc}/commercial-terms", response_model=CommercialTermsOut)
def get_commercial_terms(
    ruc: str, user: SessionUser = Depends(any_role), use_case: uc.GetCommercialTerms = Depends(deps.get_get_commercial_terms)
):
    """Nivel del cliente y sus reglas: margen, descuento máximo y días de crédito."""
    return CommercialTermsOut.from_result(use_case.execute(ruc, uc.scope_for(user)))


@router.get("/customers/{ruc}/contacts", response_model=ContactPageOut)
def list_contacts(
    ruc: str, page: int = Page, per_page: int = PerPage,
    user: SessionUser = Depends(any_role), use_case: uc.ListContacts = Depends(deps.get_list_contacts),
):
    result = use_case.execute(ruc, uc.scope_for(user), Paging(page, per_page))
    return ContactPageOut(items=[ContactOut.from_domain(c) for c in result.items], total=result.total, page=result.page, per_page=result.per_page)


@router.post("/customers/{ruc}/contacts", response_model=ContactOut, status_code=201)
def register_contact(
    ruc: str, body: ContactIn,
    user: SessionUser = Depends(any_role), use_case: uc.RegisterContact = Depends(deps.get_register_contact),
):
    """Registra que contactaste hoy al cliente y qué respondió."""
    return ContactOut.from_domain(use_case.execute(uc.RegisterContactCommand(ruc, body.outcome), user, uc.scope_for(user)))


@router.get("/customers/{ruc}/whatsapp-link", response_model=WhatsappLinkOut)
def build_whatsapp_link(
    ruc: str, message: str | None = Query(None, max_length=1000, description="Si no llega, se usa el mensaje sugerido"),
    user: SessionUser = Depends(any_role), use_case: uc.BuildWhatsappLink = Depends(deps.get_build_whatsapp_link),
):
    link = use_case.execute(ruc, uc.scope_for(user), message)
    return WhatsappLinkOut(url=link.url, message=link.message)


# Rutas del contrato aún pendientes (docs/endpoints.md): alertas (fase 3) y ficha para reunión.
for method, path, roles, summary in [
    ("GET", "/alerts", MS, "Alertas del día, ordenadas por dinero en juego"),
    ("GET", "/alerts/summary", MS, "Totales: alertas, contactados hoy, monto de 12 meses en juego"),
    ("GET", "/alerts/{alert_id}", MS, "Una alerta: producto habitual, producto cruzado, motivos y probabilidad"),
    ("GET", "/alerts/{alert_id}/explanation", MS, "Texto de IA que explica la alerta (solo cifras agregadas)"),
    ("GET", "/customers/{ruc}/brief", M, "Ficha del cliente para reunión (from, to, projection)"),
]:
    add_pending_route(router, method, path, roles, summary)
