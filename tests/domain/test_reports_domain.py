from datetime import date
from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, DataOrigin, Money
from app.modules.reports.domain.entities import DataOriginSet, Funnel, Kpi, KpiStatus, Receivable, SalesDefinition
from app.modules.reports.domain.services import AgingCalculator, KpiEvaluator, RecoveredAmountCalculator


def test_kpi_without_value_needs_warning():
    Kpi("gross_margin", None, Decimal(30), None, DataOrigin.REAL, warning="no_cost_data")
    with pytest.raises(BusinessRuleError):
        Kpi("gross_margin", None, Decimal(30), None, DataOrigin.REAL)


def test_kpi_evaluator():
    evaluator = KpiEvaluator(Decimal(10))
    assert evaluator.evaluate(Decimal(100), Decimal(100)) is KpiStatus.OK
    assert evaluator.evaluate(Decimal(95), Decimal(100)) is KpiStatus.WARN
    assert evaluator.evaluate(Decimal(80), Decimal(100)) is KpiStatus.CRITICAL
    assert evaluator.evaluate(Decimal(105), Decimal(100), higher_is_better=False) is KpiStatus.WARN


def test_data_origin_set():
    mixed = DataOriginSet(frozenset({DataOrigin.REAL, DataOrigin.SIMULATED}))
    assert mixed.overall is DataOrigin.SIMULATED and mixed.is_mixed
    with pytest.raises(BusinessRuleError):
        DataOriginSet(frozenset())


def test_funnel_rates():
    funnel = Funnel(alerts=40, contacts=10, quotations=4, converted=1, recovered_amount=Money("900"))
    assert funnel.contact_rate == Decimal("25.0")
    assert funnel.conversion_rate == Decimal("25.0")
    assert Funnel(0, 0, 0, 0, Money("0")).contact_rate is None


def test_aging_is_estimated_with_credit_days():
    calculator = AgingCalculator({"A": 60, "C": 0})
    today = date(2026, 10, 13)
    receivables = [
        Receivable("O1", "A", date(2026, 9, 1), Money("100")),  # vence 31/10: por vencer
        Receivable("O2", "C", date(2026, 9, 28), Money("50")),  # 15 días
        Receivable("O3", "C", date(2026, 5, 1), Money("25")),  # más de 90
    ]
    buckets = {bucket.label: bucket for bucket in calculator.buckets(receivables, today)}
    assert buckets["Por vencer"].amount == Money("100")
    assert buckets["1-30"].amount == Money("50")
    assert buckets["Más de 90"].amount == Money("25")
    assert all(bucket.data_origin is DataOrigin.ESTIMATED for bucket in buckets.values())


def test_recovered_amount():
    calculator = RecoveredAmountCalculator(window_days=30)
    contacts = {"R1": date(2026, 9, 1)}
    orders = [
        ("R1", date(2026, 9, 10), Money("300")),
        ("R1", date(2026, 11, 1), Money("999")),  # fuera de la ventana
        ("R2", date(2026, 9, 10), Money("500")),  # no contactado
    ]
    assert calculator.recovered(contacts, orders) == Money("300")


def test_sales_definition_excludes_cancelled_by_default():
    definition = SalesDefinition()
    assert definition.provisional
    assert [definition.counts(status) for status in ("T", "A", "C", "D", None)] == [True, True, False, True, True]
    strict = SalesDefinition(frozenset({"C", "D"}), provisional=False)
    assert not strict.counts("D")
    with pytest.raises(BusinessRuleError):
        SalesDefinition(frozenset({"X"}))
