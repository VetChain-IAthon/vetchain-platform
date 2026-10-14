from datetime import date
from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, ConflictError, DataOrigin
from app.modules.import_planning.domain.entities import CoveragePolicy, Decision, ImportSuggestion


def test_coverage_policy():
    policy = CoveragePolicy(Decimal(2), Decimal(4))
    assert policy.suggested_quantity(Decimal(150), Decimal(100)) == Decimal(250)  # 1.5 meses < 2: pedir hasta 4
    assert policy.suggested_quantity(Decimal(300), Decimal(100)) == Decimal(0)
    assert policy.suggested_quantity(Decimal(10), Decimal(0)) == Decimal(0)
    assert policy.order_before(Decimal(300), Decimal(100), date(2026, 10, 1)) == date(2026, 10, 31)
    assert policy.order_before(Decimal(100), Decimal(100), date(2026, 10, 1)) == date(2026, 10, 1)
    with pytest.raises(BusinessRuleError):
        CoveragePolicy(Decimal(4), Decimal(2))


def test_decisions_can_be_undone():
    suggestion = ImportSuggestion("P1", Decimal(10), date(2026, 11, 1), Decimal(5))
    assert suggestion.data_origin is DataOrigin.SIMULATED
    approved = suggestion.approve()
    assert approved.decision is Decision.APPROVED
    with pytest.raises(ConflictError):
        approved.reject()
    assert approved.reset().reject().decision is Decision.REJECTED
    with pytest.raises(ConflictError):
        suggestion.reset()
