from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.core.domain import BusinessRuleError, DataOrigin, Money


class KpiStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Kpi:
    """Sin datos suficientes no hay valor: va un aviso (`warning`) y no hay estado."""

    code: str
    value: Decimal | None
    target: Decimal | None
    status: KpiStatus | None
    data_origin: DataOrigin
    warning: str | None = None

    def __post_init__(self) -> None:
        if self.value is None and not self.warning:
            raise BusinessRuleError("Un KPI sin valor debe explicar por qué con un aviso.", "kpi_without_warning")
        if self.value is None and self.status is not None:
            raise BusinessRuleError("Un KPI sin valor no puede tener estado.", "kpi_status_without_value")


@dataclass(frozen=True)
class DataOriginSet:
    origins: frozenset[DataOrigin]

    def __post_init__(self) -> None:
        if not self.origins:
            raise BusinessRuleError("Toda cifra debe declarar su origen.", "missing_data_origin")

    @property
    def overall(self) -> DataOrigin:
        return DataOrigin.least_reliable(self.origins)

    @property
    def is_mixed(self) -> bool:
        return len(self.origins) > 1


@dataclass(frozen=True)
class ReportSection:
    code: str
    data_origins: DataOriginSet
    warning: str | None = None


@dataclass(frozen=True)
class Funnel:
    alerts: int
    contacts: int
    quotations: int
    converted: int
    recovered_amount: Money

    def __post_init__(self) -> None:
        if min(self.alerts, self.contacts, self.quotations, self.converted) < 0:
            raise BusinessRuleError("Los conteos del embudo no pueden ser negativos.", "invalid_funnel")

    @staticmethod
    def rate(part: int, whole: int) -> Decimal | None:
        if whole == 0:
            return None
        return (Decimal(part) / Decimal(whole) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    @property
    def contact_rate(self) -> Decimal | None:
        return self.rate(self.contacts, self.alerts)

    @property
    def conversion_rate(self) -> Decimal | None:
        return self.rate(self.converted, self.quotations)


@dataclass(frozen=True)
class AgingBucket:
    """Deuda agrupada por días de atraso. `max_days` None = sin límite superior."""

    label: str
    min_days: int
    max_days: int | None
    amount: Money
    data_origin: DataOrigin = DataOrigin.ESTIMATED

    def includes(self, days_overdue: int) -> bool:
        return days_overdue >= self.min_days and (self.max_days is None or days_overdue <= self.max_days)


@dataclass(frozen=True)
class Receivable:
    """Saldo pendiente de un pedido. El vencimiento se estima con los días de crédito del nivel.
    Sin datos reales todavía: los cobros no se enlazan con pedidos (falta el CSV de comprobantes)."""

    order_no: str
    level: str
    order_date: date
    outstanding: Money


@dataclass(frozen=True)
class MonthlyAmount:
    month: date  # primer día del mes
    order_count: int
    amount: Money  # sin IGV, solo productos veterinarios
    dispatched_amount: Money  # pedidos en estado T


@dataclass(frozen=True)
class StockLevel:
    """Stock de un producto al cierre de un mes, sumando almacenes (último saldo conocido hasta ese mes)."""

    product_code: str
    product_name: str | None
    balance: Decimal
    last_period_end: date
    data_origin: DataOrigin = DataOrigin.REAL


ORDER_STATUSES = {
    "T": "En tránsito",
    "A": "Almacén / Aprobado",
    "C": "Cancelado",
    "D": "Devuelto / Entregado",
    None: "Sin dato",
}


@dataclass(frozen=True)
class SalesDefinition:
    """Qué pedidos cuentan como "venta" según su estado (orders.status_code).

    Provisional: cuentan todos menos los cancelados (C). Falta que Mederi confirme si T (92 % de los pedidos)
    incluye entregados y si D es devuelto o entregado.
    """

    excluded_statuses: frozenset[str] = frozenset({"C"})
    provisional: bool = True

    def __post_init__(self) -> None:
        unknown = set(self.excluded_statuses) - {code for code in ORDER_STATUSES if code}
        if unknown:
            raise BusinessRuleError(f"Estado de pedido desconocido: {', '.join(sorted(unknown))}.", "unknown_status")

    def counts(self, order_status: str | None) -> bool:
        return order_status not in self.excluded_statuses

    salesperson_code: str | None = None  # solo los pedidos que tomó ese vendedor; None = todos
