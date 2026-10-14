from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.core.domain import BusinessRuleError, ForbiddenError, Money, Percentage
from app.core.domain.numbers import to_decimal


class Level(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    AT_RISK = "at_risk"
    DORMANT = "dormant"


@dataclass(frozen=True, order=True)
class Probability:
    """Probabilidad de recompra entre 0 y 1."""

    value: Decimal

    def __post_init__(self) -> None:
        value = to_decimal(self.value)
        if not Decimal(0) <= value <= Decimal(1):
            raise BusinessRuleError("La probabilidad debe estar entre 0 y 1.", "invalid_probability")
        object.__setattr__(self, "value", value)

    @property
    def as_percentage(self) -> Decimal:
        return (self.value * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PurchaseRhythm:
    """Días promedio entre pedidos de un cliente."""

    average_days: Decimal

    def __post_init__(self) -> None:
        average_days = to_decimal(self.average_days)
        if average_days <= 0:
            raise BusinessRuleError("El ritmo de compra debe ser mayor que cero.", "invalid_rhythm")
        object.__setattr__(self, "average_days", average_days.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

    @classmethod
    def from_order_dates(cls, order_dates: "list[date] | tuple[date, ...]") -> "PurchaseRhythm | None":
        """Sin al menos dos días distintos con pedido no hay ritmo."""
        days = sorted(set(order_dates))
        if len(days) < 2:
            return None
        return cls(Decimal((days[-1] - days[0]).days) / (len(days) - 1))


@dataclass(frozen=True)
class ContactOutcome:
    """Resultado de un contacto. Las 5 opciones se definen con Mederi; cuando estén, esto pasa a ser un enum."""

    value: str

    def __post_init__(self) -> None:
        value = str(self.value).strip()
        if not value:
            raise BusinessRuleError("Un contacto debe tener resultado.", "missing_contact_outcome")
        if len(value) > 30:
            raise BusinessRuleError("El resultado del contacto es demasiado largo.", "invalid_contact_outcome")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class SalespersonScope:
    """Cartera visible: gerencia ve todo (code None); un vendedor solo sus clientes."""

    salesperson_code: str | None = None

    @classmethod
    def everyone(cls) -> "SalespersonScope":
        return cls(None)

    @classmethod
    def of_salesperson(cls, code: str) -> "SalespersonScope":
        if not code:
            raise BusinessRuleError("Falta el código de vendedor.", "missing_salesperson_code")
        return cls(code)

    @property
    def is_everyone(self) -> bool:
        return self.salesperson_code is None

    def includes(self, customer_salesperson_code: str | None) -> bool:
        return self.is_everyone or customer_salesperson_code == self.salesperson_code

    def ensure_includes(self, customer_salesperson_code: str | None) -> None:
        if not self.includes(customer_salesperson_code):
            raise ForbiddenError("Este cliente no es de tu cartera.", "outside_portfolio")


@dataclass(frozen=True)
class LevelThresholds:
    """Umbrales de nivel tal como los entrega settings (anticorrupción: copia propia de customers)."""

    min_amount_b: Money
    min_amount_a: Money


@dataclass(frozen=True)
class CommercialTerms:
    level: Level
    margin: Percentage
    max_discount: Percentage
    credit_days: int


class DiscardReason(StrEnum):
    """Por qué un cliente dormido deja de considerarse para la gestión comercial."""

    BUSINESS_CLOSED = "business_closed"  # el negocio cerró o dejó de operar
    DATA_CHANGED = "data_changed"  # cambió de RUC o razón social; sigue con otro registro
    NOT_VIABLE = "not_viable"  # deuda, riesgo o ya no conviene atenderlo
    OTHER = "other"  # exige una nota
