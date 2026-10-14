"""Consultas de reportes con fechas ancladas al último pedido disponible."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.core.domain import BusinessRuleError, DateRange, Money, UnitOfWork
from app.modules.reports.domain.entities import Kpi, MonthlyAmount, SalesDefinition, StockLevel, StockPosition
from app.modules.reports.domain.ports import CustomersReadRepository, ReceiptsReadRepository, SalesReadRepository, StockReadRepository
from app.modules.reports.domain.services import ReportCalculator
from app.core.domain import DataOrigin


PRICE_KPI_TOP_PRODUCTS = 5  # productos principales para comparar precio pagado y referencia


@dataclass(frozen=True)
class ReportQuery:
    from_date: date | None = None
    to_date: date | None = None
    salesperson_code: str | None = None  # solo lo usa el reporte de ventas


@dataclass(frozen=True)
class Period:
    date_range: DateRange | None
    data_as_of: date | None
    warning: str | None


def resolve_period(sales: SalesReadRepository, query: ReportQuery) -> Period:
    as_of = sales.latest_order_date()
    end = query.to_date or as_of
    if end is None:
        if query.from_date:
            raise BusinessRuleError("Indica también la fecha final del reporte.", "missing_end_date")
        return Period(None, None, "no_order_data")
    start = query.from_date or ReportCalculator.twelve_month_start(end)
    return Period(DateRange(start, end), as_of, None)


@dataclass(frozen=True)
class CustomerAmount:
    ruc: str
    name: str
    amount: Money
    share_pct: Decimal | None
    order_count: int = 0


@dataclass(frozen=True)
class DashboardSummary:
    period: Period
    amount: Money | None
    order_count: int | None
    average_order: Money | None
    active_customers: int | None
    top_ten_share_pct: Decimal | None
    monthly: list[MonthlyAmount]
    top_customers: list[CustomerAmount]
    warnings: list[str]


class GetDashboardSummary:
    def __init__(self, sales: SalesReadRepository, customers: CustomersReadRepository, uow: UnitOfWork) -> None:
        self.sales, self.customers, self.uow = sales, customers, uow

    def execute(self, query: ReportQuery) -> DashboardSummary:
        with self.uow:
            period = resolve_period(self.sales, query)
            if period.date_range is None:
                return DashboardSummary(period, None, None, None, None, None, [], [], ["no_order_data", "alerts_unavailable"])
            definition = SalesDefinition()
            monthly = self.sales.monthly_amounts(period.date_range, definition)
            amounts = self.customers.amounts_by_customer(period.date_range, definition)
            total = Money.total([month.amount for month in monthly])
            count = sum(month.order_count for month in monthly)
            names = self.customers.names_by_ruc([ruc for ruc, *_ in amounts[:10]])
            top = [CustomerAmount(ruc, names.get(ruc, ruc), amount, ReportCalculator.share(amount, total), orders)
                   for ruc, amount, orders in amounts[:10]]
            warnings = ["alerts_unavailable", "order_statuses_provisional"]
            if not monthly:
                warnings.append("no_order_data")
            return DashboardSummary(period, total if monthly else None, count if monthly else None,
                                    ReportCalculator.average(total, count), len(amounts),
                                    ReportCalculator.share(Money.total([amount for _, amount, _ in amounts[:10]]), total),
                                    monthly, top, warnings)


@dataclass(frozen=True)
class ProductAmount:
    code: str
    name: str
    amount: Money


@dataclass(frozen=True)
class CategoryAmount:
    code: str | None
    amount: Money


@dataclass(frozen=True)
class PricePoint:
    """Precio pagado frente a la referencia (último precio pagado a cualquier cliente). Estimado: no hay lista oficial."""

    code: str
    name: str
    amount: Money
    quantity: Decimal
    reference_price: Money | None

    @property
    def average_price(self) -> Money | None:
        return self.amount.divided_by(self.quantity) if self.quantity > 0 else None

    @property
    def below_reference_pct(self) -> Decimal | None:
        paid = self.average_price
        if paid is None or self.reference_price is None or self.reference_price.amount <= 0:
            return None
        return ((self.reference_price.amount - paid.amount) * 100 / self.reference_price.amount).quantize(Decimal("0.1"))


def weighted_below_reference(points: list[PricePoint]) -> Decimal | None:
    """Promedio ponderado por monto de cuánto bajo la referencia se vendió; solo productos con referencia."""
    priced = [p for p in points if p.below_reference_pct is not None]
    weight = sum((p.amount.amount for p in priced), start=Decimal(0))
    if not weight:
        return None
    return (sum((p.below_reference_pct * p.amount.amount for p in priced), start=Decimal(0)) / weight).quantize(Decimal("0.1"))


@dataclass(frozen=True)
class SalesReport:
    period: Period
    monthly: list[MonthlyAmount]
    products: list[ProductAmount]
    categories: list[CategoryAmount]
    amount: Money | None
    order_count: int | None
    warnings: list[str]
    price_points: list[PricePoint] = field(default_factory=list)
    invoice_discount: Money | None = None
    list_amount: Money | None = None


class GetSalesReport:
    def __init__(self, sales: SalesReadRepository, uow: UnitOfWork) -> None:
        self.sales, self.uow = sales, uow

    def execute(self, query: ReportQuery) -> SalesReport:
        with self.uow:
            period = resolve_period(self.sales, query)
            if period.date_range is None:
                return SalesReport(period, [], [], [], None, None, ["no_order_data", "no_cost_data"])
            definition = SalesDefinition(salesperson_code=query.salesperson_code or None)
            monthly = self.sales.monthly_amounts(period.date_range, definition)
            points = [PricePoint(*row) for row in self.sales.product_price_points(period.date_range, definition, PRICE_KPI_TOP_PRODUCTS)]
            discount, list_amount = self.sales.invoice_discount(period.date_range, definition)
            products = [ProductAmount(code, name, amount) for code, name, amount
                        in self.sales.amounts_by_product(period.date_range, definition)]
            categories = [CategoryAmount(code, amount) for code, amount
                          in self.sales.amounts_by_category(period.date_range, definition)]
            return SalesReport(period, monthly, products, categories,
                               Money.total([m.amount for m in monthly]) if monthly else None,
                               sum(m.order_count for m in monthly) if monthly else None,
                               ["no_cost_data", "order_statuses_provisional", "category_unconfirmed"] +
                               (["no_order_data"] if not monthly else []),
                               points, discount, list_amount)


@dataclass(frozen=True)
class CustomersReport:
    period: Period
    master_count: int
    active_count: int | None
    no_orders_12m: int | None
    amount: Money | None
    top_ten_share_pct: Decimal | None
    top_customers: list[CustomerAmount]
    warnings: list[str]


class GetCustomersReport:
    def __init__(self, sales: SalesReadRepository, customers: CustomersReadRepository, uow: UnitOfWork) -> None:
        self.sales, self.customers, self.uow = sales, customers, uow

    def execute(self, query: ReportQuery) -> CustomersReport:
        with self.uow:
            period = resolve_period(self.sales, query)
            master = self.customers.master_count()
            if period.date_range is None:
                return CustomersReport(period, master, None, None, None, None, [], ["no_order_data", "risk_factors_unconfigured"])
            amounts = self.customers.amounts_by_customer(period.date_range, SalesDefinition())
            total = Money.total([amount for _, amount, _ in amounts])
            names = self.customers.names_by_ruc([ruc for ruc, *_ in amounts[:10]])
            top = [CustomerAmount(ruc, names.get(ruc, ruc), amount, ReportCalculator.share(amount, total), orders)
                   for ruc, amount, orders in amounts[:10]]
            return CustomersReport(period, master, len(amounts), master - len(amounts),
                                   total if amounts else None,
                                   ReportCalculator.share(Money.total([amount for _, amount, _ in amounts[:10]]), total),
                                   top, ["risk_factors_unconfigured"] + (["no_order_data"] if not amounts else []))


@dataclass(frozen=True)
class StockReport:
    period: Period
    stock_as_of: date | None
    items: list[StockPosition]
    warnings: list[str]


class GetStockReport:
    def __init__(self, sales: SalesReadRepository, stock: StockReadRepository, uow: UnitOfWork) -> None:
        self.sales, self.stock, self.uow = sales, stock, uow

    def execute(self, query: ReportQuery) -> StockReport:
        with self.uow:
            period = resolve_period(self.sales, query)
            stock_as_of = self.stock.latest_period_end()
            if stock_as_of is None:
                return StockReport(period, None, [], ["no_stock_data", "stock_balance_unconfirmed", "no_lot_data"])
            end = query.to_date or stock_as_of
            cutoff = min(end, stock_as_of)
            levels = self.stock.levels_at(cutoff.year, cutoff.month)
            demand = self.sales.units_by_product(DateRange(ReportCalculator.twelve_month_start(cutoff), cutoff), SalesDefinition())
            items = [StockPosition(level, *demand.get(level.product_code, (Decimal(0), None)), cutoff) for level in levels]
            return StockReport(period, cutoff, items, ["stock_balance_unconfirmed", "no_lot_data", "no_cost_data"])


@dataclass(frozen=True)
class SalespersonAmount:
    code: str
    name: str
    amount: Money
    order_count: int
    customer_count: int
    share_pct: Decimal | None


@dataclass(frozen=True)
class SalespeopleReport:
    period: Period
    amount: Money | None
    items: list[SalespersonAmount]
    warnings: list[str]


class GetSalespeopleReport:
    def __init__(self, sales: SalesReadRepository, uow: UnitOfWork) -> None:
        self.sales, self.uow = sales, uow

    def execute(self, query: ReportQuery) -> SalespeopleReport:
        with self.uow:
            period = resolve_period(self.sales, query)
            if period.date_range is None:
                return SalespeopleReport(period, None, [], ["no_order_data", "alerts_unavailable"])
            rows = self.sales.amounts_by_salesperson(period.date_range, SalesDefinition())
            total = Money.total([row[2] for row in rows])
            items = [SalespersonAmount(code, name, amount, orders, customers,
                                       ReportCalculator.share(amount, total))
                     for code, name, amount, orders, customers in rows]
            return SalespeopleReport(period, total if rows else None, items,
                                     ["alerts_unavailable", "portfolio_provisional"] +
                                     (["no_order_data"] if not rows else []))


@dataclass(frozen=True)
class MonthlyReceipts:
    month: date
    amount: Money
    count: int


@dataclass(frozen=True)
class Payer:
    ruc: str
    name: str
    amount: Money
    count: int


@dataclass(frozen=True)
class ReceivablesReport:
    """Cobros registrados en el período (reales). La deuda pendiente y vencida no se calcula: los cobros no se
    enlazan con pedidos ni facturas (aviso `receipts_not_linked`)."""

    period: Period
    collected: Money | None
    receipt_count: int | None
    monthly: list[MonthlyReceipts]
    top_payers: list[Payer]
    warnings: list[str]


TOP_PAYERS = 10


class GetReceivablesReport:
    def __init__(self, sales: SalesReadRepository, uow: UnitOfWork, receipts: ReceiptsReadRepository | None = None) -> None:
        self.sales, self.uow, self.receipts = sales, uow, receipts

    def execute(self, query: ReportQuery) -> ReceivablesReport:
        with self.uow:
            period = resolve_period(self.sales, query)
            if period.date_range is None or self.receipts is None:
                return ReceivablesReport(period, None, None, [], [], ["receipts_not_linked"])
            monthly = [MonthlyReceipts(*row) for row in self.receipts.monthly_receipts(period.date_range)]
            payers = [Payer(*row) for row in self.receipts.top_payers(period.date_range, TOP_PAYERS)]
            return ReceivablesReport(period, Money.total([m.amount for m in monthly]), sum(m.count for m in monthly),
                                     monthly, payers, ["receipts_not_linked"])


@dataclass(frozen=True)
class ReportEntry:
    code: str
    name: str
    path: str
    data_origin: DataOrigin | None
    warning: str | None


class ListReports:
    def execute(self) -> list[ReportEntry]:
        return [
            ReportEntry("sales", "Pedidos y productos", "/reports/sales", DataOrigin.REAL, "no_cost_data"),
            ReportEntry("customers", "Clientes y concentración", "/reports/customers", DataOrigin.REAL, "risk_factors_unconfigured"),
            ReportEntry("stock", "Stock", "/reports/stock", DataOrigin.REAL, "stock_balance_unconfirmed"),
            ReportEntry("salespeople", "Vendedores", "/reports/salespeople", DataOrigin.REAL, "portfolio_provisional"),
            ReportEntry("receivables", "Cartera y cobranza", "/reports/receivables", None, "receipts_not_linked"),
            ReportEntry("kpis", "Indicadores clave", "/reports/kpis", DataOrigin.REAL, "targets_unconfigured"),
            ReportEntry("funnel", "Seguimiento comercial", "/reports/funnel", None, "alerts_unavailable"),
        ]


@dataclass(frozen=True)
class KpiReport:
    period: Period
    items: list[Kpi]
    warnings: list[str]


class GetKpis:
    def __init__(self, summary: GetDashboardSummary, sales: SalesReadRepository | None = None, uow: UnitOfWork | None = None) -> None:
        self.summary, self.sales, self.uow = summary, sales, uow

    def execute(self, query: ReportQuery) -> KpiReport:
        result = self.summary.execute(query)
        below = self._below_reference_pct(result.period)
        values = {"ordered_amount": result.amount.amount if result.amount else None,
                  "order_count": Decimal(result.order_count) if result.order_count is not None else None,
                  "average_order": result.average_order.amount if result.average_order else None,
                  "active_customers": Decimal(result.active_customers) if result.active_customers is not None else None,
                  "top_ten_share_pct": result.top_ten_share_pct}
        items = [Kpi(code, value, None, None, DataOrigin.REAL,
                     "no_order_data" if value is None else None) for code, value in values.items()]
        if self.sales is not None:
            items.append(Kpi("below_reference_pct", below, None, None, DataOrigin.ESTIMATED,
                             "no_order_data" if below is None else None))
        return KpiReport(result.period, items, ["targets_unconfigured", *result.warnings])

    def _below_reference_pct(self, period: Period) -> Decimal | None:
        """Cuánto por debajo del último precio pagado (la referencia) se vendieron en promedio los 5 productos de mayor monto,
        ponderado por monto. Estimado: no hay lista de precios oficial."""
        if self.sales is None or self.uow is None or period.date_range is None:
            return None
        with self.uow:
            points = [PricePoint(*row) for row in self.sales.product_price_points(period.date_range, SalesDefinition(), PRICE_KPI_TOP_PRODUCTS)]
        return weighted_below_reference(points)


class GetFunnelReport:
    def __init__(self, sales: SalesReadRepository, uow: UnitOfWork) -> None:
        self.sales, self.uow = sales, uow

    def execute(self, query: ReportQuery) -> Period:
        with self.uow:
            return resolve_period(self.sales, query)
