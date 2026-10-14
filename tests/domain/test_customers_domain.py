from datetime import date
from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, ForbiddenError, Money, Ruc
from app.modules.customers.domain.entities import Alert, CustomerActivity
from app.modules.customers.domain.services import (
    AlertPrioritizer,
    DormancyEvaluator,
    LevelClassifier,
    WhatsappLinkBuilder,
)
from app.modules.customers.domain.value_objects import (
    ContactOutcome,
    CustomerStatus,
    Level,
    LevelThresholds,
    Probability,
    PurchaseRhythm,
    SalespersonScope,
)

RUC = Ruc("20123456789")


def test_purchase_rhythm():
    assert PurchaseRhythm.from_order_dates([date(2026, 1, 1)]) is None
    rhythm = PurchaseRhythm.from_order_dates([date(2026, 1, 1), date(2026, 1, 31), date(2026, 3, 2), date(2026, 3, 2)])
    assert rhythm.average_days == Decimal("30.0")


def test_dormancy_evaluator():
    evaluator = DormancyEvaluator(Decimal("1.5"), Decimal("3"), PurchaseRhythm(Decimal(60)))
    rhythm = PurchaseRhythm(Decimal(30))
    today = date(2026, 10, 13)
    assert evaluator.evaluate(date(2026, 9, 20), rhythm, today) is CustomerStatus.ACTIVE  # 23 días
    assert evaluator.evaluate(date(2026, 8, 20), rhythm, today) is CustomerStatus.AT_RISK  # 54 días
    assert evaluator.evaluate(date(2026, 6, 1), rhythm, today) is CustomerStatus.DORMANT  # 134 días
    assert evaluator.evaluate(date(2026, 8, 20), None, today) is CustomerStatus.ACTIVE  # usa 60 días
    assert evaluator.evaluate(None, None, today) is CustomerStatus.DORMANT
    with pytest.raises(BusinessRuleError):
        DormancyEvaluator(Decimal("3"), Decimal("2"), rhythm)


def test_level_classifier():
    classifier = LevelClassifier(LevelThresholds(Money("10000"), Money("50000")))
    assert classifier.classify(Money("60000")) is Level.A
    assert classifier.classify(Money("100")) is Level.C


def test_alert_prioritizer():
    assert AlertPrioritizer.money_at_stake(CustomerActivity(RUC, Money("12000"), 4)) == Money("3000")
    assert AlertPrioritizer.money_at_stake(CustomerActivity(RUC, Money("0"), 0)) == Money("0")

    def alert(money, probability):
        return Alert(RUC, date(2026, 10, 13), Probability(probability), Money(money), ("rhythm_broken",))

    low, high, tie = alert("100", "0.9"), alert("500", "0.2"), alert("500", "0.8")
    assert AlertPrioritizer.prioritize([low, high, tie]) == [tie, high, low]


def test_alert_needs_reason():
    with pytest.raises(BusinessRuleError):
        Alert(RUC, date(2026, 10, 13), Probability("0.5"), Money("1"), ())


def test_contact_needs_outcome():
    with pytest.raises(BusinessRuleError):
        ContactOutcome("  ")


def test_salesperson_scope():
    SalespersonScope.everyone().ensure_includes("V09")
    scope = SalespersonScope.of_salesperson("V01")
    scope.ensure_includes("V01")
    with pytest.raises(ForbiddenError):
        scope.ensure_includes("V02")


def test_whatsapp_link():
    link = WhatsappLinkBuilder.build("+51 987 654 321", "Hola, ¿cómo va?")
    assert link == "https://wa.me/51987654321?text=Hola%2C%20%C2%BFc%C3%B3mo%20va%3F"
    with pytest.raises(BusinessRuleError):
        WhatsappLinkBuilder.build("01 4445555", "Hola")
    with pytest.raises(BusinessRuleError):
        WhatsappLinkBuilder.build(None, "Hola")
