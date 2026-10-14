from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.core.domain import DataOrigin, Money, Percentage


class QuotationStatus(StrEnum):
    ISSUED = "issued"
    CONVERTED = "converted"
    EXPIRED = "expired"


class Level(StrEnum):
    A = "A"
    B = "B"
    C = "C"


@dataclass(frozen=True)
class ReferencePrice:
    """Precio de referencia de un producto y de dónde sale (p. ej. último precio pagado: real)."""

    price: Money
    origin: DataOrigin


@dataclass(frozen=True)
class Margin:
    """Margen sobre el neto sin IGV. Puede ser negativo. Nulo con aviso cuando faltan costos."""

    pct: Decimal | None
    warning: str | None = None

    @classmethod
    def unknown(cls) -> "Margin":
        return cls(None, "no_cost_data")

    @classmethod
    def from_amounts(cls, net: Money, cost: Money) -> "Margin":
        if net.amount == 0:
            return cls.unknown()
        pct = ((net.amount - cost.amount) / net.amount * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return cls(pct)

    @property
    def is_known(self) -> bool:
        return self.pct is not None

    def is_below(self, minimum: Percentage) -> bool:
        return self.pct is not None and self.pct < minimum.value


@dataclass(frozen=True)
class ApprovalStatus:
    """required: la política pide aprobación. confirmed: gerencia la dio. note: comentario de quien aprueba."""

    required: bool
    reasons: tuple[str, ...] = ()
    confirmed: bool = False
    note: str | None = None

    def confirm(self, note: str | None) -> "ApprovalStatus":
        return ApprovalStatus(self.required, self.reasons, True, (note or "").strip() or None)

    @property
    def blocks_issue(self) -> bool:
        return self.required and not self.confirmed


@dataclass(frozen=True)
class CustomerTerms:
    """Condiciones comerciales del cliente (copia propia de quotations, viene de customers)."""

    level: Level
    max_discount: Percentage
    margin: Percentage
    credit_days: int


@dataclass(frozen=True)
class PricingTerms:
    """Reglas de precios (copia propia de quotations, viene de settings)."""

    igv_rate: Percentage
    quotation_validity_days: int
    min_margin: Percentage
