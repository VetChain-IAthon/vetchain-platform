from datetime import date
from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, DataOrigin
from app.modules.prediction.domain.entities import DemandForecast, ModelNotLoadedError, RepurchaseProbability


def test_probability_range():
    assert RepurchaseProbability(Decimal("0.123456")).value == Decimal("0.1235")
    with pytest.raises(BusinessRuleError):
        RepurchaseProbability(Decimal("1.2"))


def test_forecast_rules():
    DemandForecast("P1", date(2026, 11, 1), Decimal("10"), DataOrigin.ESTIMATED)
    with pytest.raises(BusinessRuleError):
        DemandForecast("P1", date(2026, 11, 15), Decimal("10"), DataOrigin.ESTIMATED)
    with pytest.raises(BusinessRuleError):
        DemandForecast("P1", date(2026, 11, 1), Decimal("-1"), DataOrigin.ESTIMATED)


def test_model_not_loaded_is_a_business_error():
    error = ModelNotLoadedError()
    assert isinstance(error, BusinessRuleError)
    assert error.code == "model_not_loaded"
