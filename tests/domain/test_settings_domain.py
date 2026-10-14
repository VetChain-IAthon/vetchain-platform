import pytest

from app.core.domain import BusinessRuleError, Money, Percentage
from app.modules.settings.domain.entities import CustomerLevelRule, Level, LevelRules, LevelThresholds, PricingSettings
from app.modules.settings.domain.services import LevelPolicy


def _rule(level, discount="5"):
    return CustomerLevelRule(level, Percentage(discount), Percentage("20"), 30)


def test_level_rules_need_a_b_c():
    rules = LevelRules((_rule(Level.C), _rule(Level.A), _rule(Level.B)))
    assert [rule.level for rule in rules.rules] == [Level.A, Level.B, Level.C]
    with pytest.raises(BusinessRuleError):
        LevelRules((_rule(Level.A), _rule(Level.B)))


def test_replace_one_level():
    rules = LevelRules((_rule(Level.A), _rule(Level.B), _rule(Level.C)))
    assert rules.replace(_rule(Level.B, "12")).for_level(Level.B).max_discount == Percentage("12")


def test_thresholds_a_at_least_b():
    with pytest.raises(BusinessRuleError):
        LevelThresholds(Money("5000"), Money("1000"))


def test_level_policy():
    policy = LevelPolicy(LevelThresholds(Money("10000"), Money("50000")))
    assert policy.classify(Money("50000")) is Level.A
    assert policy.classify(Money("10000")) is Level.B
    assert policy.classify(Money("9999.99")) is Level.C


def test_pricing_validity_days():
    with pytest.raises(BusinessRuleError):
        PricingSettings(Percentage(18), 0, Percentage(15), Percentage(5))
    with pytest.raises(BusinessRuleError):
        CustomerLevelRule(Level.A, Percentage(5), Percentage(20), -1)
