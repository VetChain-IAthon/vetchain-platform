"""Lectura agregada para reportes desde las tablas de Defontana (solo lectura)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.domain import DateRange, Money
from app.infrastructure.db.repositories import queries
from app.infrastructure.db.source_models import Customer, Order, OrderLine, Product, Salesperson, StockBalance
from app.modules.reports.domain.entities import MonthlyAmount, SalesDefinition, StockLevel


def _seller(definition: SalesDefinition) -> list:
    return [Order.salesperson_code == definition.salesperson_code] if definition.salesperson_code else []


def _excluded(definition: SalesDefinition) -> tuple[str, ...]:
    return tuple(sorted(definition.excluded_statuses))


class SqlSalesReadRepository:
    """Implementa SalesReadRepository. Montos sin IGV, solo productos veterinarios."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_order_date(self) -> date | None:
        return self._session.scalar(select(func.max(Order.order_date)))

    def monthly_amounts(self, date_range: DateRange, definition: SalesDefinition) -> list[MonthlyAmount]:
        rows = queries.monthly_sales(
            self._session, date_range.from_date, date_range.to_date, exclude_statuses=_excluded(definition),
            salesperson_code=definition.salesperson_code,
        )
        return [
            MonthlyAmount(
                month=date.fromisoformat(row["month"] + "-01"),
                order_count=row["order_count"],
                amount=Money(row["amount"]),
                dispatched_amount=Money(row["dispatched_amount"]),
            )
            for row in rows
        ]

    def amounts_by_category(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, Money]]:
        rows = queries.sales_by_category(
            self._session, date_range.from_date, date_range.to_date, exclude_statuses=_excluded(definition),
            salesperson_code=definition.salesperson_code,
        )
        return [(row["category_code"], Money(row["amount"])) for row in rows]

    def amounts_by_product(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, str, Money]]:
        query = (
            select(Product.code, Product.name, func.sum(OrderLine.line_total).label("amount"))
            .select_from(Order).join(OrderLine, OrderLine.order_no == Order.order_no)
            .join(Product, Product.code == OrderLine.product_code)
            .where(Order.order_date >= date_range.from_date, Order.order_date <= date_range.to_date,
                   Product.is_core_product.is_(True), OrderLine.is_bonus.is_(False),
                   or_(Order.status_code.is_(None), Order.status_code.not_in(tuple(definition.excluded_statuses))),
                   *_seller(definition))
            .group_by(Product.code, Product.name).order_by(func.sum(OrderLine.line_total).desc(), Product.code)
        )
        return [(row.code, row.name, Money(row.amount)) for row in self._session.execute(query)]

    def product_price_points(self, date_range: DateRange, definition: SalesDefinition, limit: int) -> list[tuple[str, str, Money, Decimal, Money | None]]:
        query = (
            select(Product.code, Product.name, func.sum(OrderLine.line_total).label("amount"), func.sum(OrderLine.quantity).label("quantity"))
            .select_from(Order).join(OrderLine, OrderLine.order_no == Order.order_no)
            .join(Product, Product.code == OrderLine.product_code)
            .where(Order.order_date >= date_range.from_date, Order.order_date <= date_range.to_date,
                   Product.is_core_product.is_(True), OrderLine.is_bonus.is_(False),
                   or_(Order.status_code.is_(None), Order.status_code.not_in(tuple(definition.excluded_statuses))),
                   *_seller(definition))
            .group_by(Product.code, Product.name).order_by(func.sum(OrderLine.line_total).desc(), Product.code).limit(limit)
        )
        rows = list(self._session.execute(query))
        references = queries.last_paid_prices(self._session, [row.code for row in rows], date_range.to_date)
        return [(row.code, row.name, Money(row.amount), row.quantity, Money(references[row.code]) if row.code in references else None)
                for row in rows]

    def units_by_product(self, date_range: DateRange, definition: SalesDefinition) -> dict[str, tuple[Decimal, date]]:
        query = (
            select(OrderLine.product_code, func.sum(OrderLine.quantity).label("units"), func.max(Order.order_date).label("last_sale"))
            .select_from(Order).join(OrderLine, OrderLine.order_no == Order.order_no)
            .where(Order.order_date >= date_range.from_date, Order.order_date <= date_range.to_date, OrderLine.is_bonus.is_(False),
                   or_(Order.status_code.is_(None), Order.status_code.not_in(tuple(definition.excluded_statuses))), *_seller(definition))
            .group_by(OrderLine.product_code)
        )
        return {row.product_code: (row.units, row.last_sale) for row in self._session.execute(query)}

    def invoice_discount(self, date_range: DateRange, definition: SalesDefinition) -> tuple[Money, Money]:
        query = (
            select(func.sum(OrderLine.line_total).label("amount"), func.sum(OrderLine.quantity * OrderLine.unit_price).label("list_amount"))
            .select_from(Order).join(OrderLine, OrderLine.order_no == Order.order_no)
            .join(Product, Product.code == OrderLine.product_code)
            .where(Order.order_date >= date_range.from_date, Order.order_date <= date_range.to_date,
                   Product.is_core_product.is_(True), OrderLine.is_bonus.is_(False),
                   or_(Order.status_code.is_(None), Order.status_code.not_in(tuple(definition.excluded_statuses))),
                   *_seller(definition))
        )
        row = self._session.execute(query).one()
        amount, list_amount = Money(row.amount or 0), Money(row.list_amount or 0)
        # Cada total de línea viene redondeado: sin descuentos, la resta puede dar unos céntimos negativos.
        return max(list_amount - amount, Money.zero()), list_amount

    def amounts_by_salesperson(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, str, Money, int, int]]:
        query = (
            select(Order.salesperson_code, Salesperson.name, func.sum(OrderLine.line_total).label("amount"),
                   func.count(func.distinct(Order.order_no)).label("order_count"),
                   func.count(func.distinct(Order.ruc)).label("customer_count"))
            .select_from(Order).join(OrderLine, OrderLine.order_no == Order.order_no)
            .join(Product, Product.code == OrderLine.product_code)
            .join(Salesperson, Salesperson.code == Order.salesperson_code)
            .where(Order.order_date >= date_range.from_date, Order.order_date <= date_range.to_date,
                   Product.is_core_product.is_(True), OrderLine.is_bonus.is_(False),
                   or_(Order.status_code.is_(None), Order.status_code.not_in(tuple(definition.excluded_statuses))))
            .group_by(Order.salesperson_code, Salesperson.name)
            .order_by(func.sum(OrderLine.line_total).desc(), Order.salesperson_code)
        )
        return [(row.salesperson_code, row.name, Money(row.amount), row.order_count, row.customer_count)
                for row in self._session.execute(query)]


class SqlCustomersReadRepository:
    """Implementa CustomersReadRepository de reports (concentración de clientes)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def master_count(self) -> int:
        return self._session.scalar(select(func.count()).select_from(Customer)) or 0

    def names_by_ruc(self, rucs: list[str]) -> dict[str, str]:
        if not rucs:
            return {}
        return dict(self._session.execute(select(Customer.ruc, Customer.name).where(Customer.ruc.in_(rucs))).all())

    def amounts_by_customer(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, Money, int]]:
        rows = queries.amounts_by_customer(
            self._session, date_range.from_date, date_range.to_date, exclude_statuses=_excluded(definition)
        )
        return [(row["ruc"], Money(row["amount"]), row["order_count"]) for row in rows]


class SqlStockReadRepository:
    """Implementa StockReadRepository. El saldo del kardex es POR CONFIRMAR (¿stock al cierre?)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_period_end(self) -> date | None:
        return self._session.scalar(
            select(func.max(StockBalance.period_end))
            .join(Product, Product.code == StockBalance.product_code)
            .where(Product.is_core_product.is_(True))
        )

    def levels_at(self, year: int, month: int) -> list[StockLevel]:
        core_codes = set(self._session.scalars(
            select(Product.code).where(Product.is_core_product.is_(True))
        ))
        return [
            StockLevel(row["product_code"], row["product_name"], row["balance"], row["last_period_end"])
            for row in queries.stock_at(self._session, year, month)
            if row["product_code"] in core_codes
        ]
