from datetime import date
from decimal import Decimal
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

    def product_price_points(self, date_range: DateRange, definition: SalesDefinition, limit: int) -> list[tuple[str, str, Money, Decimal, Money | None]]:
        """Los `limit` productos de mayor monto: (código, nombre, monto sin bonificadas, cantidad, último precio pagado hasta el fin del rango).
        El último precio pagado es la referencia de precio (estimada): no hay lista de precios oficial."""
        ...

    def invoice_discount(self, date_range: DateRange, definition: SalesDefinition) -> tuple[Money, Money]:
        """(descuento de línea en factura, monto antes de ese descuento), sin IGV y sin bonificadas."""
        ...

    def units_by_product(self, date_range: DateRange, definition: SalesDefinition) -> dict[str, tuple[Decimal, date]]:
        """Por producto: unidades pedidas (sin bonificadas) y fecha del último pedido en el rango."""
        ...

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

