from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum

from app.core.domain import BusinessRuleError, ConflictError, DataOrigin
from app.core.domain.numbers import to_decimal

_DAYS_PER_MONTH = Decimal(30)


class Decision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CoveragePolicy:
    """Reglas deterministas de cobertura mínima y máxima para una fase con datos validados.

    Si el stock cubre menos que el mínimo, se pide hasta llegar al máximo.
    """

    min_months: Decimal
    max_months: Decimal

    def __post_init__(self) -> None:
        min_months, max_months = to_decimal(self.min_months), to_decimal(self.max_months)
        if not Decimal(0) < min_months <= max_months:
            raise BusinessRuleError("Se necesita 0 < cobertura mínima <= cobertura máxima.", "invalid_coverage")
        object.__setattr__(self, "min_months", min_months)
        object.__setattr__(self, "max_months", max_months)

    def coverage_months(self, stock: Decimal, monthly_demand: Decimal) -> Decimal | None:
        return None if monthly_demand <= 0 else to_decimal(stock) / to_decimal(monthly_demand)

    def suggested_quantity(self, stock: Decimal, monthly_demand: Decimal) -> Decimal:
        coverage = self.coverage_months(stock, monthly_demand)
        if coverage is None or coverage >= self.min_months:
            return Decimal(0)
        return (self.max_months * to_decimal(monthly_demand) - to_decimal(stock)).to_integral_value(ROUND_CEILING)

    def order_before(self, stock: Decimal, monthly_demand: Decimal, today: date) -> date | None:
        """Fecha en que el stock baja a la cobertura mínima. Si ya está debajo, hoy."""
        coverage = self.coverage_months(stock, monthly_demand)
        if coverage is None:
            return None
        days_left = max((coverage - self.min_months) * _DAYS_PER_MONTH, Decimal(0))
        return today + timedelta(days=int(days_left))


@dataclass(frozen=True)
class ImportSuggestion:
    """Sugerencia de dominio para una fase con datos validados; la pantalla inicial usa un escenario simulado."""

    product_code: str
    suggested_quantity: Decimal
    order_before: date | None
    monthly_demand: Decimal
    supplier: str | None = None
    decision: Decision = Decision.PENDING
    data_origin: DataOrigin = DataOrigin.SIMULATED
    warning: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if to_decimal(self.suggested_quantity) < 0:
            raise BusinessRuleError("La cantidad sugerida no puede ser negativa.", "invalid_quantity")

    def approve(self) -> "ImportSuggestion":
        return self._decide(Decision.APPROVED)

    def reject(self) -> "ImportSuggestion":
        return self._decide(Decision.REJECTED)

    def reset(self) -> "ImportSuggestion":
        """Deshace la decisión."""
        if self.decision is Decision.PENDING:
            raise ConflictError("La sugerencia ya está pendiente.", "already_pending")
        return replace(self, decision=Decision.PENDING)

    def _decide(self, decision: Decision) -> "ImportSuggestion":
        if self.decision is not Decision.PENDING:
            raise ConflictError("La sugerencia ya tiene una decisión. Vuelve a pendiente para cambiarla.", "already_decided")
        return replace(self, decision=decision)
