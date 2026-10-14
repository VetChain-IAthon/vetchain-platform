from datetime import date
from typing import Protocol

from app.core.domain import DataOrigin, DateRange, Money
from app.modules.reports.domain.entities import Funnel, MonthlyAmount, Receivable, SalesDefinition, StockLevel


class SalesReadRepository(Protocol):
    def latest_order_date(self) -> date | None: ...

    def monthly_amounts(self, date_range: DateRange, definition: SalesDefinition) -> list[MonthlyAmount]: ...

    def amounts_by_category(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, Money]]:
        """Monto por categoría de producto (products.category_code, POR CONFIRMAR)."""
        ...

    def amounts_by_product(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, str, Money]]: ...

    def amounts_by_salesperson(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, str, Money, int, int]]: ...


class CustomersReadRepository(Protocol):
    def master_count(self) -> int: ...

    def names_by_ruc(self, rucs: list[str]) -> dict[str, str]: ...

    def amounts_by_customer(self, date_range: DateRange, definition: SalesDefinition) -> list[tuple[str, Money, int]]:
        """(RUC, monto, pedidos), de mayor a menor monto. Para la concentración de clientes. Los RUC no salen de este módulo hacia la IA."""
        ...


class StockReadRepository(Protocol):
    def latest_period_end(self) -> date | None: ...

    def levels_at(self, year: int, month: int) -> list[StockLevel]: ...


class ReceivablesReadRepository(Protocol):
    def outstanding(self, as_of: date) -> list[Receivable]: ...


class FunnelReadRepository(Protocol):
    def funnel(self, date_range: DateRange) -> Funnel: ...


class DataOriginProvider(Protocol):
    def origin_of(self, source: str) -> DataOrigin: ...


class SettingsGateway(Protocol):
    def credit_days_by_level(self) -> dict[str, int]: ...

