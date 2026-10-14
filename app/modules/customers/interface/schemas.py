from datetime import date
from decimal import Decimal
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


class AtRiskCustomerOut(BaseModel):
    ruc: str
    name: str
    last_order_date: date
    days_since_last_order: int = Field(description="Días entre el último pedido y la fecha de corte de los datos")
    purchase_rhythm_days: JsonNumber | None = Field(description="Días promedio entre pedidos en 12 meses; null con menos de dos")
    money_at_stake: JsonNumber = Field(description="Pedido promedio de 12 meses, sin IGV")
    amount_12m: JsonNumber = Field(description="Pedidos de 12 meses, sin IGV")

    @classmethod
    def from_result(cls, item: uc.AtRiskCustomer) -> "AtRiskCustomerOut":
        return cls(
            ruc=item.customer.ruc.value, name=item.customer.name, last_order_date=item.last_order_date,
            days_since_last_order=item.days_since_last_order,
            purchase_rhythm_days=item.rhythm.average_days if item.rhythm else None,
            money_at_stake=item.money_at_stake.amount, amount_12m=item.amount_12m.amount,
        )


class AtRiskCustomerPageOut(BaseModel):
    items: list[AtRiskCustomerOut]
    total: int
    page: int
    per_page: int
    data_as_of: date | None
    at_risk_factor: JsonNumber = Field(description="Veces el ritmo de compra a partir de las cuales el cliente está en riesgo")
    default_rhythm_days: JsonNumber = Field(description="Ritmo usado cuando el cliente tiene menos de dos pedidos")
    warning: Literal["risk_factors_provisional"] = "risk_factors_provisional"
    data_origin: Literal["estimated"] = "estimated"

    @classmethod
    def from_result(cls, result: uc.AtRiskCustomerList) -> "AtRiskCustomerPageOut":
        return cls(
            items=[AtRiskCustomerOut.from_result(item) for item in result.page.items],
            total=result.page.total, page=result.page.page, per_page=result.page.per_page,
            data_as_of=result.data_as_of, at_risk_factor=result.at_risk_factor, default_rhythm_days=result.default_rhythm_days,
        )


class FollowUpBucketOut(BaseModel):
    outcome: str | None = Field(description="Resultado del último contacto; null = sin contactar")
    customer_count: int
    money_at_stake: JsonNumber = Field(description="Suma del pedido promedio de cada cliente, sin IGV")


class SalespersonFollowUpOut(BaseModel):
    salesperson_code: str
    salesperson_name: str
    customer_count: int
    money_at_stake: JsonNumber
    buckets: list[FollowUpBucketOut]


class AtRiskFollowUpOut(BaseModel):
    items: list[SalespersonFollowUpOut]
    warning: Literal["portfolio_provisional"] = "portfolio_provisional"
    data_origin: Literal["estimated"] = "estimated"

    @classmethod
    def from_result(cls, result: "list[uc.SalespersonFollowUp]") -> "AtRiskFollowUpOut":
        return cls(items=[
            SalespersonFollowUpOut(
                salesperson_code=f.salesperson_code, salesperson_name=f.salesperson_name, customer_count=f.customer_count,
                money_at_stake=f.money_at_stake.amount,
                buckets=[FollowUpBucketOut(outcome=b.outcome, customer_count=b.customer_count, money_at_stake=b.money_at_stake.amount)
                         for b in f.buckets],
            )
            for f in result
        ])


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


class BriefProductOut(BaseModel):
    product_code: str
    product_name: str
    category_code: str | None = Field(description="Categoría de Defontana (POR CONFIRMAR)")
    order_count: int
    quantity: JsonNumber
    amount: JsonNumber = Field(description="Sin IGV, sin bonificadas")
    average_price: JsonNumber | None = Field(description="Precio pagado promedio por unidad, sin IGV")
    reference_price: JsonNumber | None = Field(description="Último precio pagado por cualquier cliente (estimado)")
    below_reference_pct: JsonNumber | None = Field(description="% bajo la referencia; negativo si pagó más")
    last_order_date: date


class BriefMonthOut(BaseModel):
    month: str = Field(description="AAAA-MM")
    amount: JsonNumber
    order_count: int


class CustomerBriefOut(BaseModel):
    ruc: str
    name: str
    level: str | None = Field(description="Por el monto de 12 meses; null mientras gerencia no defina los umbrales")
    credit_days: int | None
    salesperson_code: str | None
    salesperson_name: str | None
    salesperson_share_pct: JsonNumber | None = Field(description="% del monto del período atendido por su vendedor asignado")
    date_from: date
    date_to: date
    data_as_of: date | None
    projection: Literal["month", "semester", "year"]
    amount: JsonNumber = Field(description="Pedidos del período, sin IGV, solo veterinarios")
    order_count: int
    average_order_amount: JsonNumber
    share_pct: JsonNumber = Field(description="% del monto de todos los clientes en el período")
    rank: int | None
    ranked_customers: int = Field(description="Clientes con pedidos en el período")
    purchase_rhythm_days: JsonNumber | None
    last_order_date: date | None
    expected_next_order_date: date | None
    days_since_last_order: int | None = Field(description="Hasta date_to")
    days_late: int | None = Field(description="Días por encima de su ritmo de compra; 0 si va al día")
    invoice_discount: JsonNumber = Field(description="Descuento de línea en los pedidos del período, sin IGV")
    list_amount: JsonNumber = Field(description="Monto antes del descuento de línea")
    monthly: list[BriefMonthOut]
    order_dates: list[date]
    products: list[BriefProductOut]
    below_reference_pct: JsonNumber | None = Field(description="Promedio ponderado por monto, solo productos con referencia")
    projected_amount: JsonNumber | None = Field(description="Siempre null hasta que exista el modelo de predicción")
    estimated_profit: JsonNumber | None = Field(description="Siempre null hasta que haya costos validados")
    warnings: list[str]
    data_origin: DataOriginReal = "real"

    @classmethod
    def from_result(cls, brief: uc.CustomerBrief) -> "CustomerBriefOut":
        customer = brief.customer
        priced = [p for p in brief.products if p.below_reference_pct is not None]
        weight = sum((p.purchase.amount.amount for p in priced), start=0)
        below = (sum(p.below_reference_pct * p.purchase.amount.amount for p in priced) / weight).quantize(Decimal("0.1")) if weight else None
        return cls(
            ruc=customer.ruc.value, name=customer.name, level=brief.level.value if brief.level else None,
            credit_days=brief.credit_days, salesperson_code=customer.salesperson_code,
            salesperson_name=brief.salesperson_name, salesperson_share_pct=brief.salesperson_share_pct,
            date_from=brief.date_from, date_to=brief.date_to, data_as_of=brief.data_as_of, projection=brief.projection,
            amount=brief.amount.amount, order_count=brief.order_count, average_order_amount=brief.average_order_amount.amount,
            share_pct=brief.share_pct, rank=brief.rank, ranked_customers=brief.ranked_customers,
            purchase_rhythm_days=brief.rhythm.average_days if brief.rhythm else None,
            last_order_date=brief.last_order_date, expected_next_order_date=brief.expected_next_order,
            days_since_last_order=brief.days_since_last_order, days_late=brief.days_late,
            invoice_discount=brief.invoice_discount.amount, list_amount=brief.list_amount.amount,
            monthly=[BriefMonthOut(month=m.month, amount=m.amount.amount, order_count=m.order_count) for m in brief.monthly],
            order_dates=list(brief.order_dates),
            products=[BriefProductOut(
                product_code=p.purchase.product_code, product_name=p.purchase.product_name, category_code=p.purchase.category_code,
                order_count=p.purchase.order_count, quantity=p.purchase.quantity, amount=p.purchase.amount.amount,
                average_price=p.purchase.average_price.amount if p.purchase.average_price else None,
                reference_price=p.reference_price.amount if p.reference_price else None,
                below_reference_pct=p.below_reference_pct, last_order_date=p.purchase.last_order_date,
            ) for p in brief.products],
            below_reference_pct=below, projected_amount=None, estimated_profit=None, warnings=list(brief.warnings),
        )
