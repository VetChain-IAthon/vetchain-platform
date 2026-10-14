from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.core.domain import BusinessRuleError, DataOrigin, Money, Ruc
from app.core.domain.numbers import to_decimal


class ModelNotLoadedError(BusinessRuleError):
    """Sin modelo no se inventan probabilidades."""

    def __init__(self) -> None:
        super().__init__(
            "El modelo de predicción no está disponible. Hay que entrenarlo y cargar models/model.json.",
            "model_not_loaded",
        )


@dataclass(frozen=True)
class CustomerFeatures:
    ruc: Ruc
    days_since_last_order: int
    order_frequency_days: Decimal | None
    average_order_amount: Money
    families: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.days_since_last_order < 0:
            raise BusinessRuleError("Los días desde el último pedido no pueden ser negativos.", "invalid_days")


@dataclass(frozen=True, order=True)
class RepurchaseProbability:
    value: Decimal

    def __post_init__(self) -> None:
        value = to_decimal(self.value)
        if not Decimal(0) <= value <= Decimal(1):
            raise BusinessRuleError("La probabilidad debe estar entre 0 y 1.", "invalid_probability")
        object.__setattr__(self, "value", value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class ModelInfo:
    version: str
    trained_on: date
    auc: Decimal
    top_decile_precision: Decimal


@dataclass(frozen=True)
class MonthlyDemand:
    """Cantidad pedida de un producto en un mes (dato real de los pedidos)."""

    product_code: str
    month: date  # primer día del mes
    quantity: Decimal


@dataclass(frozen=True)
class DemandForecast:
    product_code: str
    month: date  # primer día del mes
    quantity: Decimal
    origin: DataOrigin

    def __post_init__(self) -> None:
        if to_decimal(self.quantity) < 0:
            raise BusinessRuleError("La demanda pronosticada no puede ser negativa.", "invalid_forecast")
        if self.month.day != 1:
            raise BusinessRuleError("El mes del pronóstico debe ser el primer día del mes.", "invalid_month")
