from dataclasses import dataclass
from decimal import Decimal

from app.core.domain.errors import BusinessRuleError
from app.core.domain.numbers import to_decimal


@dataclass(frozen=True, order=True)
class Percentage:
    """Porcentaje entre 0 y 100."""

    value: Decimal

    def __post_init__(self) -> None:
        value = to_decimal(self.value)
        if not Decimal(0) <= value <= Decimal(100):
            raise BusinessRuleError("El porcentaje debe estar entre 0 y 100.", "invalid_percentage")
        object.__setattr__(self, "value", value)

    @property
    def fraction(self) -> Decimal:
        return self.value / Decimal(100)

    @classmethod
    def zero(cls) -> "Percentage":
        return cls(Decimal(0))
