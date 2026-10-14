from dataclasses import dataclass
from datetime import date

from app.core.domain.errors import BusinessRuleError


@dataclass(frozen=True)
class DateRange:
    """Rango de fechas cerrado (incluye ambos extremos). En HTTP se reciben como `from` y `to`."""

    from_date: date
    to_date: date

    def __post_init__(self) -> None:
        if self.from_date > self.to_date:
            raise BusinessRuleError("La fecha inicial debe ser anterior o igual a la final.", "invalid_date_range")

    def contains(self, day: date) -> bool:
        return self.from_date <= day <= self.to_date

    @property
    def days(self) -> int:
        return (self.to_date - self.from_date).days + 1
