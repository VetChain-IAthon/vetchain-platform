from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.domain.numbers import to_decimal
from app.core.domain.percentage import Percentage

_CENT = Decimal("0.01")


@dataclass(frozen=True, order=True)
class Money:
    """Monto en soles (PEN) con 2 decimales. Sin IGV salvo que el nombre del campo lo diga (`_with_tax`)."""

    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", to_decimal(self.amount).quantize(_CENT, rounding=ROUND_HALF_UP))

    @classmethod
    def zero(cls) -> "Money":
        return cls(Decimal(0))

    def __add__(self, other: "Money") -> "Money":
        return Money(self.amount + other.amount)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.amount - other.amount)

    def times(self, factor: Decimal | int) -> "Money":
        return Money(self.amount * to_decimal(factor))

    def percent(self, percentage: Percentage) -> "Money":
        return Money(self.amount * percentage.fraction)

    def divided_by(self, divisor: Decimal | int) -> "Money":
        divisor = to_decimal(divisor)
        if divisor == 0:
            raise ZeroDivisionError("No se puede dividir un monto entre cero.")
        return Money(self.amount / divisor)

    @property
    def is_negative(self) -> bool:
        return self.amount < 0

    @staticmethod
    def total(amounts: "list[Money] | tuple[Money, ...]") -> "Money":
        result = Money.zero()
        for amount in amounts:
            result = result + amount
        return result
