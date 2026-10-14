from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, Money
from app.modules.explanations.domain.entities import AggregatedFigures, AllowedQueryType, InsightQuery
from app.modules.explanations.domain.services import PrivacyGuard


def test_aggregated_figures_fill_the_prompt():
    figures = AggregatedFigures(45, Decimal("30.0"), Decimal("0.734"), Money("1250.5"), ("Antiparasitarios",))
    assert figures.as_prompt_values() == {
        "days_since_last_purchase": "45",
        "purchase_frequency_days": "30.0",
        "repurchase_probability_pct": "73",
        "avg_order_amount": "1250.50",
        "top_families": "Antiparasitarios",
    }


def test_insight_query_only_allowed_filters():
    InsightQuery(AllowedQueryType.SALES_BY_FAMILY, filters=(("region", "Lima"),))
    with pytest.raises(BusinessRuleError):
        InsightQuery(AllowedQueryType.SALES_BY_FAMILY, filters=(("ruc", "20123456789"),))


@pytest.mark.parametrize(
    "text",
    [
        "¿Cuánto compró el 20123456789?",
        "ventas de cliente@vet.pe",
        "llamar al 987654321",
        "¿Qué compra Veterinaria San Martín?",
    ],
)
def test_privacy_guard_rejects_identifying_text(text):
    guard = PrivacyGuard({"Veterinaria San Martín"})
    with pytest.raises(BusinessRuleError):
        guard.check_text(text)


def test_privacy_guard_allows_aggregated_questions():
    PrivacyGuard({"Veterinaria San Martín"}).check_text("¿Qué familia vendió más en 2026 en Lima?")


def test_privacy_guard_checks_query_values():
    query = InsightQuery(AllowedQueryType.TOP_PRODUCTS, filters=(("region", "20123456789"),))
    with pytest.raises(BusinessRuleError):
        PrivacyGuard().check_query(query)
