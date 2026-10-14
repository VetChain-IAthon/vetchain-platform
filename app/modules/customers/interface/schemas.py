from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import JsonNumber
from app.modules.customers.application import use_cases as uc
from app.modules.customers.domain.entities import Contact, OrderSummary, ProductPurchase

DataOriginReal = Literal["real"]


class CustomerSummaryOut(BaseModel):
    ruc: str
    name: str
    customer_type: str | None = Field(description="company | person | other")
    region: str | None
    salesperson_code: str | None
    level: str | None = Field(description="A, B o C; null mientras gerencia no defina los umbrales")
    amount_12m: JsonNumber = Field(description="Pedidos de 12 meses, sin IGV, solo veterinarios")
    order_count_12m: int
    last_order_date: date | None = Field(description="Último pedido en todo el historial")


class CustomerListItemOut(CustomerSummaryOut):
    share_pct: JsonNumber = Field(description="% del monto de 12 meses de la cartera visible")

    @classmethod
    def from_result(cls, item: uc.CustomerListItem) -> "CustomerListItemOut":
        return cls(**_summary(item.standing), share_pct=item.share_pct)


class CustomerPageOut(BaseModel):
    items: list[CustomerListItemOut]
    total: int
    page: int
    per_page: int
    total_amount_12m: JsonNumber
    data_as_of: date | None = Field(description="Fecha del último pedido cargado: la ventana de 12 meses termina aquí")
    levels_configured: bool
    data_origin: DataOriginReal = "real"


class DormantCustomerOut(BaseModel):
    ruc: str
    name: str
    customer_type: str | None = Field(description="company | person | other")
    region: str | None
    order_count: int = Field(description="Pedidos en todo el historial")
    lifetime_amount: JsonNumber = Field(description="Monto histórico de pedidos, sin IGV, solo veterinarios")
    last_order_date: date | None = Field(description="null si no tiene pedidos en los archivos")

    @classmethod
    def from_result(cls, item: uc.DormantCustomer) -> "DormantCustomerOut":
        customer, act = item.customer, item.lifetime
        return cls(
            ruc=customer.ruc.value, name=customer.name, customer_type=customer.customer_type, region=customer.region,
            order_count=act.order_count, lifetime_amount=act.amount.amount, last_order_date=act.last_order_date,
        )


class DormantTypeCountsOut(BaseModel):
    all: int
    company: int
    person: int


class DormantCustomerPageOut(BaseModel):
    items: list[DormantCustomerOut]
    total: int
    page: int
    per_page: int
    customer_count: int = Field(description="Clientes de la cartera visible")
    dormant_count: int = Field(description="Sin pedidos en los 12 meses, antes de buscar o filtrar")
    ordered_before_count: int = Field(description="Dormidos que sí tuvieron pedidos antes")
    type_counts: DormantTypeCountsOut = Field(description="Dormidos que coinciden con la búsqueda, por tipo")
    data_as_of: date | None = Field(description="Fecha del último pedido cargado: la ventana de 12 meses termina aquí")
    data_origin: DataOriginReal = "real"

    @classmethod
    def from_result(cls, result: uc.DormantCustomerList) -> "DormantCustomerPageOut":
        counts = result.type_counts
        return cls(
            items=[DormantCustomerOut.from_result(item) for item in result.page.items],
            total=result.page.total, page=result.page.page, per_page=result.page.per_page,
            customer_count=result.customer_count, dormant_count=result.dormant_count,
            ordered_before_count=result.ordered_before_count,
            type_counts=DormantTypeCountsOut(all=counts.get("all", 0), company=counts.get("company", 0), person=counts.get("person", 0)),
            data_as_of=result.data_as_of,
        )


class CustomerDetailOut(CustomerSummaryOut):
    phone: str | None
    email: str | None
    average_order_amount_12m: JsonNumber
    purchase_rhythm_days: JsonNumber | None = Field(description="Días promedio entre pedidos; null con menos de dos")
    lifetime_amount: JsonNumber
    lifetime_order_count: int
    first_order_date: date | None
    data_as_of: date | None
    levels_configured: bool
    data_origin: DataOriginReal = "real"

    @classmethod
    def from_result(cls, detail: uc.CustomerDetail) -> "CustomerDetailOut":
        customer = detail.standing.customer
        return cls(
            **_summary(detail.standing),
            phone=customer.phone,
            email=customer.email,
            average_order_amount_12m=detail.average_order_amount_12m.amount,
            purchase_rhythm_days=detail.rhythm.average_days if detail.rhythm else None,
            lifetime_amount=detail.lifetime.amount.amount,
            lifetime_order_count=detail.lifetime.order_count,
            first_order_date=detail.first_order_date,
            data_as_of=detail.data_as_of,
            levels_configured=detail.levels_configured,
        )


def _summary(standing) -> dict:
    customer, act = standing.customer, standing.activity_12m
    return dict(
        ruc=customer.ruc.value,
        name=customer.name,
        customer_type=customer.customer_type,
        region=customer.region,
        salesperson_code=customer.salesperson_code,
        level=standing.level.value if standing.level else None,
        amount_12m=act.amount.amount,
        order_count_12m=act.order_count,
        last_order_date=standing.last_order_date,
    )


class OrderOut(BaseModel):
    order_no: str
    order_date: date
    amount: JsonNumber = Field(description="Sin IGV (subtotal − descuento). Un pedido no es una venta facturada")
    total_with_tax: JsonNumber
    status_code: str | None = Field(description="T en tránsito, A almacén, C cancelado, D devuelto/entregado (por confirmar)")
    salesperson_code: str

    @classmethod
    def from_domain(cls, order: OrderSummary) -> "OrderOut":
        return cls(
            order_no=order.order_no, order_date=order.order_date, amount=order.amount.amount,
            total_with_tax=order.total_with_tax.amount, status_code=order.status_code, salesperson_code=order.salesperson_code,
        )


class OrderPageOut(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    per_page: int
    data_origin: DataOriginReal = "real"


class ProductPurchaseOut(BaseModel):
    product_code: str
    product_name: str
    category_code: str | None
    times_ordered: int
    total_quantity: JsonNumber
    amount: JsonNumber = Field(description="Sin IGV y sin líneas bonificadas")
    last_order_date: date

    @classmethod
    def from_domain(cls, item: ProductPurchase) -> "ProductPurchaseOut":
        return cls(
            product_code=item.product_code, product_name=item.product_name, category_code=item.category_code,
            times_ordered=item.times_ordered, total_quantity=item.total_quantity, amount=item.amount.amount,
            last_order_date=item.last_order_date,
        )


class ProductPurchasesOut(BaseModel):
    items: list[ProductPurchaseOut]
    data_origin: DataOriginReal = "real"


class CommercialTermsOut(BaseModel):
    level: str
    margin_pct: JsonNumber
    max_discount_pct: JsonNumber
    credit_days: int
    amount_12m: JsonNumber = Field(description="Monto de 12 meses con el que se calculó el nivel")
    data_as_of: date | None

    @classmethod
    def from_result(cls, result: uc.CustomerTerms) -> "CommercialTermsOut":
        terms = result.terms
        return cls(
            level=terms.level.value, margin_pct=terms.margin.value, max_discount_pct=terms.max_discount.value,
            credit_days=terms.credit_days, amount_12m=result.amount_12m.amount, data_as_of=result.data_as_of,
        )


class ContactIn(BaseModel):
    outcome: str = Field(min_length=1, max_length=30, description="Qué respondió el cliente (las opciones se definen con Mederi)")


class ContactOut(BaseModel):
    id: int
    ruc: str
    user_id: int
    outcome: str
    contact_date: date
    alert_id: int | None

    @classmethod
    def from_domain(cls, contact: Contact) -> "ContactOut":
        return cls(
            id=contact.id, ruc=contact.ruc.value, user_id=contact.user_id, outcome=contact.outcome.value,
            contact_date=contact.contact_date, alert_id=contact.alert_id,
        )


class ContactPageOut(BaseModel):
    items: list[ContactOut]
    total: int
    page: int
    per_page: int


class WhatsappLinkOut(BaseModel):
    url: str
    message: str
