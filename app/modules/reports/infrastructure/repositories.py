"""Lectura agregada para reportes desde las tablas de Defontana (solo lectura)."""
from datetime import date

from sqlalchemy.orm import Session

from app.core.domain import DateRange, Money
from app.infrastructure.db.repositories import queries
from app.modules.reports.domain.entities import MonthlyAmount, SalesDefinition, StockLevel


def _excluded(definition: SalesDefinition) -> tuple[str, ...]:
    return tuple(sorted(definition.excluded_statuses))


class SqlSalesReadRepository:
    """Implementa SalesReadRepository. Montos sin IGV, solo productos veterinarios."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def monthly_amounts(self, date_range: DateRange, definition: SalesDefinition) -> list[MonthlyAmount]:
        rows = queries.monthly_sales(
            self._session, date_range.from_date, date_range.to_date, exclude_statuses=_excluded(definition)
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
            self._session, date_range.from_date, date_range.to_date, exclude_statuses=_excluded(definition)
        )
        return [(row["category_code"], Money(row["amount"])) for row in rows]


class SqlCustomersReadRepository:
    """Implementa CustomersReadRepository de reports (concentración de clientes)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def amounts_by_customer(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, Money]]:
        rows = queries.amounts_by_customer(
            self._session, date_range.from_date, date_range.to_date, exclude_statuses=_excluded(definition)
        )
        return [(row["ruc"], Money(row["amount"])) for row in rows]


class SqlStockReadRepository:
    """Implementa StockReadRepository. El saldo del kardex es POR CONFIRMAR (¿stock al cierre?)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def levels_at(self, year: int, month: int) -> list[StockLevel]:
        return [
            StockLevel(row["product_code"], row["product_name"], row["balance"], row["last_period_end"])
            for row in queries.stock_at(self._session, year, month)
        ]
