from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.core.domain import BusinessRuleError, DataOrigin, DateRange, Money
from app.core.domain.numbers import to_decimal


@dataclass(frozen=True)
class AggregatedFigures:
    """Lo único que Gemini recibe sobre un cliente. Por construcción no tiene nombre ni RUC."""

    days_since_last_purchase: int
    purchase_frequency_days: Decimal | None
    repurchase_probability: Decimal  # 0 a 1
    average_order_amount: Money
    top_families: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        probability = to_decimal(self.repurchase_probability)
        if not Decimal(0) <= probability <= Decimal(1):
            raise BusinessRuleError("La probabilidad debe estar entre 0 y 1.", "invalid_probability")
        if self.days_since_last_purchase < 0:
            raise BusinessRuleError("Los días sin comprar no pueden ser negativos.", "invalid_days")
        object.__setattr__(self, "repurchase_probability", probability)

    def as_prompt_values(self) -> dict[str, str]:
        """Valores para los placeholders de prompts/alert_explanation.md."""
        frequency = self.purchase_frequency_days
        return {
            "days_since_last_purchase": str(self.days_since_last_purchase),
            "purchase_frequency_days": "sin dato" if frequency is None else str(frequency),
            "repurchase_probability_pct": str((self.repurchase_probability * 100).quantize(Decimal("1"), ROUND_HALF_UP)),
            "avg_order_amount": str(self.average_order_amount.amount),
            "top_families": ", ".join(self.top_families) or "sin dato",
        }


class ExplanationSource(StrEnum):
    AI = "ai"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class Explanation:
    text: str
    source: ExplanationSource


class AllowedQueryType(StrEnum):
    """Lista cerrada de consultas que se pueden responder. Propuesta inicial, a validar con gerencia."""

    SALES_BY_MONTH = "sales_by_month"
    SALES_BY_FAMILY = "sales_by_family"
    TOP_PRODUCTS = "top_products"
    CUSTOMERS_BY_STATUS = "customers_by_status"
    CUSTOMERS_BY_LEVEL = "customers_by_level"
    CUSTOMERS_BY_REGION = "customers_by_region"
    RECEIVABLES_AGING = "receivables_aging"
    SALESPERSON_PERFORMANCE = "salesperson_performance"


ALLOWED_FILTERS = frozenset({"family", "product_code", "region", "level", "status", "salesperson_code"})


@dataclass(frozen=True)
class InsightQuery:
    query_type: AllowedQueryType
    date_range: DateRange | None = None
    filters: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        unknown = {key for key, _ in self.filters} - ALLOWED_FILTERS
        if unknown:
            raise BusinessRuleError(f"Filtro no permitido: {', '.join(sorted(unknown))}.", "filter_not_allowed")


@dataclass(frozen=True)
class InsightAnswer:
    text: str
    sources: tuple[str, ...]
    data_origin: DataOrigin


@dataclass(frozen=True)
class AggregatedResult:
    """Resultado de una consulta permitida: filas agregadas, sin datos de clientes individuales."""

    rows: tuple[dict[str, str], ...]
    sources: tuple[str, ...]
    data_origin: DataOrigin
