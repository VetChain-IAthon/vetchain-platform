"""Respuestas HTTP de reportes: cifras y origen siempre visibles."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import JsonNumber
from app.modules.reports.application import use_cases as uc


class PeriodOut(BaseModel):
    from_date: date | None
    to_date: date | None
    data_as_of: date | None
    warning: str | None

    @classmethod
    def from_domain(cls, period: uc.Period):
        dates = period.date_range
        return cls(from_date=dates.from_date if dates else None, to_date=dates.to_date if dates else None,
                   data_as_of=period.data_as_of, warning=period.warning)


class MonthlyAmountOut(BaseModel):
    month: date
    order_count: int
    amount: JsonNumber
    dispatched_amount: JsonNumber
    data_origin: Literal["real"] = "real"

    @classmethod
    def from_domain(cls, item):
        return cls(month=item.month, order_count=item.order_count, amount=item.amount.amount,
                   dispatched_amount=item.dispatched_amount.amount)


class CustomerAmountOut(BaseModel):
    ruc: str
    name: str
    amount: JsonNumber
    share_pct: JsonNumber | None
    order_count: int = Field(description="Pedidos del período")
    data_origin: Literal["real"] = "real"

    @classmethod
    def from_domain(cls, item):
        return cls(ruc=item.ruc, name=item.name, amount=item.amount.amount, share_pct=item.share_pct, order_count=item.order_count)


class DashboardSummaryOut(BaseModel):
    period: PeriodOut
    amount: JsonNumber | None
    order_count: int | None
    average_order: JsonNumber | None
    active_customers: int | None
    top_ten_share_pct: JsonNumber | None
    monthly: list[MonthlyAmountOut]
    top_customers: list[CustomerAmountOut]
    warnings: list[str]
    data_origin: Literal["real"] = "real"

    @classmethod
    def from_domain(cls, result: uc.DashboardSummary):
        return cls(period=PeriodOut.from_domain(result.period), amount=result.amount.amount if result.amount else None,
                   order_count=result.order_count,
                   average_order=result.average_order.amount if result.average_order else None,
                   active_customers=result.active_customers, top_ten_share_pct=result.top_ten_share_pct,
                   monthly=[MonthlyAmountOut.from_domain(x) for x in result.monthly],
                   top_customers=[CustomerAmountOut.from_domain(x) for x in result.top_customers],
                   warnings=result.warnings)


class ProductAmountOut(BaseModel):
    code: str
    name: str
    amount: JsonNumber
    data_origin: Literal["real"] = "real"


class CategoryAmountOut(BaseModel):
    code: str | None
    amount: JsonNumber
    data_origin: Literal["real"] = "real"


class PricePointOut(BaseModel):
    code: str
    name: str
    quantity: JsonNumber
    amount: JsonNumber = Field(description="Sin IGV, sin bonificadas")
    average_price: JsonNumber | None
    reference_price: JsonNumber | None = Field(description="Último precio pagado por cualquier cliente hasta el fin del período (estimado)")
    below_reference_pct: JsonNumber | None


class SalesReportOut(BaseModel):
    period: PeriodOut
    monthly: list[MonthlyAmountOut]
    products: list[ProductAmountOut]
    categories: list[CategoryAmountOut]
    amount: JsonNumber | None
    order_count: int | None
    margin_pct: JsonNumber | None = None
    price_points: list[PricePointOut] = Field(default_factory=list, description="Los 5 productos de mayor monto: precio pagado frente a la referencia")
    below_reference_pct: JsonNumber | None = Field(None, description="Promedio ponderado por monto de price_points (estimado)")
    invoice_discount: JsonNumber | None = Field(None, description="Descuento de línea en factura del período, sin IGV")
    list_amount: JsonNumber | None = Field(None, description="Monto antes del descuento de línea")
    warnings: list[str]
    data_origin: Literal["real"] = "real"

    @classmethod
    def from_domain(cls, result: uc.SalesReport):
        return cls(period=PeriodOut.from_domain(result.period),
                   monthly=[MonthlyAmountOut.from_domain(x) for x in result.monthly],
                   products=[ProductAmountOut(code=x.code, name=x.name, amount=x.amount.amount) for x in result.products],
                   categories=[CategoryAmountOut(code=x.code, amount=x.amount.amount) for x in result.categories],
                   amount=result.amount.amount if result.amount else None, order_count=result.order_count,
                   price_points=[PricePointOut(code=p.code, name=p.name, quantity=p.quantity, amount=p.amount.amount,
                                               average_price=p.average_price.amount if p.average_price else None,
                                               reference_price=p.reference_price.amount if p.reference_price else None,
                                               below_reference_pct=p.below_reference_pct) for p in result.price_points],
                   below_reference_pct=uc.weighted_below_reference(result.price_points),
                   invoice_discount=result.invoice_discount.amount if result.invoice_discount else None,
                   list_amount=result.list_amount.amount if result.list_amount else None,
                   warnings=result.warnings)


class CustomersReportOut(BaseModel):
    period: PeriodOut
    master_count: int
    active_count: int | None
    no_orders_12m: int | None
    amount: JsonNumber | None
    top_ten_share_pct: JsonNumber | None
    top_customers: list[CustomerAmountOut]
    at_risk_count: int | None = None
    dormant_count: int | None = None
    warnings: list[str]
    data_origin: Literal["real"] = "real"

    @classmethod
    def from_domain(cls, result: uc.CustomersReport):
        return cls(period=PeriodOut.from_domain(result.period), master_count=result.master_count,
                   active_count=result.active_count, no_orders_12m=result.no_orders_12m,
                   amount=result.amount.amount if result.amount else None,
                   top_ten_share_pct=result.top_ten_share_pct,
                   top_customers=[CustomerAmountOut.from_domain(x) for x in result.top_customers],
                   warnings=result.warnings)


class StockItemOut(BaseModel):
    product_code: str
    product_name: str | None
    balance: JsonNumber
    last_period_end: date
    units_12m: JsonNumber = Field(description="Unidades pedidas en los 12 meses hasta la fecha del stock, sin bonificadas")
    last_sale_date: date | None
    coverage_days: JsonNumber | None = Field(description="Días que alcanza el stock al ritmo de 12 meses (estimado)")
    status: Literal["out_with_demand", "slow", "overstock", "normal", "out"] = Field(
        description="Provisional: sobrestock > 120 días de cobertura; lento = sin pedidos en 90 días")
    data_origin: Literal["real"] = "real"
    warning: Literal["stock_balance_unconfirmed"] = "stock_balance_unconfirmed"


class StockReportOut(BaseModel):
    period: PeriodOut
    stock_as_of: date | None
    items: list[StockItemOut]
    warnings: list[str]
    data_origin: Literal["real"] = "real"

    @classmethod
    def from_domain(cls, result: uc.StockReport):
        return cls(period=PeriodOut.from_domain(result.period), stock_as_of=result.stock_as_of,
                   items=[StockItemOut(product_code=x.level.product_code, product_name=x.level.product_name,
                                       balance=x.level.balance, last_period_end=x.level.last_period_end,
                                       units_12m=x.units_12m, last_sale_date=x.last_sale_date,
                                       coverage_days=x.coverage_days, status=x.status) for x in result.items],
                   warnings=result.warnings)


class SalespersonAmountOut(BaseModel):
    code: str
    name: str
    amount: JsonNumber
    order_count: int
    customer_count: int
    share_pct: JsonNumber | None
    data_origin: Literal["real"] = "real"


class SalespeopleReportOut(BaseModel):
    period: PeriodOut
    amount: JsonNumber | None
    items: list[SalespersonAmountOut]
    warnings: list[str]
    data_origin: Literal["real"] = "real"

    @classmethod
    def from_domain(cls, result: uc.SalespeopleReport):
        return cls(period=PeriodOut.from_domain(result.period), amount=result.amount.amount if result.amount else None,
                   items=[SalespersonAmountOut(code=x.code, name=x.name, amount=x.amount.amount,
                                               order_count=x.order_count, customer_count=x.customer_count,
                                               share_pct=x.share_pct) for x in result.items], warnings=result.warnings)


class ReceiptMonthOut(BaseModel):
    month: date
    amount: JsonNumber
    count: int


class PayerOut(BaseModel):
    ruc: str
    name: str
    amount: JsonNumber
    count: int


class ReceivablesReportOut(BaseModel):
    period: PeriodOut
    outstanding_amount: JsonNumber | None = Field(None, description="Siempre null: los cobros no se enlazan con pedidos")
    overdue_amount: JsonNumber | None = Field(None, description="Siempre null: falta el vencimiento de cada factura")
    collected_amount: JsonNumber | None = Field(None, description="Cobrado en el período, tal como viene en cobros (real)")
    receipt_count: int | None = None
    monthly_collected: list[ReceiptMonthOut] = Field(default_factory=list)
    top_payers: list[PayerOut] = Field(default_factory=list, description="Los 10 clientes que más pagaron en el período")
    warnings: list[str] = ["receipts_not_linked"]
    data_origin: Literal["real"] = "real"

    @classmethod
    def from_domain(cls, result: uc.ReceivablesReport):
        return cls(period=PeriodOut.from_domain(result.period),
                   collected_amount=result.collected.amount if result.collected else None, receipt_count=result.receipt_count,
                   monthly_collected=[ReceiptMonthOut(month=m.month, amount=m.amount.amount, count=m.count) for m in result.monthly],
                   top_payers=[PayerOut(ruc=p.ruc, name=p.name, amount=p.amount.amount, count=p.count) for p in result.top_payers],
                   warnings=result.warnings)


class ReportEntryOut(BaseModel):
    code: str
    name: str
    path: str
    data_origin: str | None
    warning: str | None


class ReportCatalogOut(BaseModel):
    items: list[ReportEntryOut]
    total: int
    page: int = 1
    per_page: int = 7


class KpiOut(BaseModel):
    code: str
    value: JsonNumber | None
    target: JsonNumber | None
    status: str | None
    data_origin: str
    warning: str | None


class KpiReportOut(BaseModel):
    period: PeriodOut
    items: list[KpiOut]
    warnings: list[str]


class FunnelReportOut(BaseModel):
    period: PeriodOut
    alerts: int | None = None
    contacts: int | None = None
    quotations: int | None = None
    converted: int | None = None
    recovered_amount: JsonNumber | None = None
    warnings: list[str] = ["alerts_unavailable", "conversion_unavailable"]
