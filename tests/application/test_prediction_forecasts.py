"""La comparación usa meses anteriores y mantiene separado el horizonte acumulado."""
from datetime import date
from decimal import Decimal

import pytest

from app.modules.prediction.application.use_cases import CompareForecasts, ExplainForecast
from app.modules.prediction.domain.entities import MonthlyDemand


class History:
    def latest_order_date(self):
        return date(2025, 2, 5)

    def first_month(self, product_code):
        return date(2024, 1, 1)

    def monthly_history(self, product_code, scenario, cutoff):
        assert (product_code, scenario, cutoff) == ("P1", "B", date(2024, 12, 1))
        return [MonthlyDemand("P1", date(2024, month, 1), Decimal(month)) for month in range(1, 13)]


class Model:
    def predict(self, scenario, horizon, features):
        assert (scenario, horizon) == ("B", 3)
        assert features["mes_num"] == 1
        assert features["meses_historicos_disponibles"] == 12
        assert features["B_lag_12m"] == 1
        assert features["B_lag_1m"] == 12
        assert features["B_promedio_6m"] == 9.5
        return 25.25


def test_forecast_compares_same_product_and_horizon():
    result = CompareForecasts(History(), Model()).execute("P1", "B", 3, date(2024, 12, 1))
    assert result.moving_average_6m == 28.5
    assert result.extra_trees == 25.25
    assert result.forecast_start_month == "2025-01"


def test_future_cutoff_is_rejected():
    with pytest.raises(Exception, match="mes cerrado"):
        CompareForecasts(History(), Model()).execute("P1", "B", 3, date(2025, 2, 1))


def test_explanation_only_sends_aggregate_figures_and_marks_gemini():
    class Generator:
        def generate(self, prompt):
            assert "P1" not in prompt
            assert "28.5" in prompt and "25.25" in prompt
            return "Son cantidades estimadas."

    answer = ExplainForecast(CompareForecasts(History(), Model()), Generator()).execute("P1", "B", 3, date(2024, 12, 1))
    assert answer.source == "gemini"


def test_explanation_failure_uses_labeled_fallback():
    class Generator:
        def generate(self, prompt):
            raise RuntimeError("API unavailable")

    answer = ExplainForecast(CompareForecasts(History(), Model()), Generator()).execute("P1", "B", 3, date(2024, 12, 1))
    assert answer.source == "fallback"
    assert "25.25" in answer.text
