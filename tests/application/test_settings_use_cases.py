from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, NotFoundError
from app.modules.settings.application import use_cases as uc
from app.modules.settings.domain.entities import Level
from tests.application.fakes import FakeUnitOfWork, InMemorySettingsRepository


@pytest.fixture()
def repo():
    return InMemorySettingsRepository()


def test_pricing_not_configured_then_replaced(repo):
    uow = FakeUnitOfWork()
    with pytest.raises(NotFoundError, match="aún no están configuradas"):
        uc.GetPricing(repo, uow).execute()
    uc.ReplacePricing(repo, uow).execute(uc.ReplacePricingCommand(Decimal(18), 15, Decimal(20), Decimal(5)))
    pricing = uc.GetPricing(repo, uow).execute()
    assert pricing.igv_rate.value == Decimal(18) and pricing.quotation_validity_days == 15
    assert uow.commits == 1
    with pytest.raises(BusinessRuleError):
        uc.ReplacePricing(repo, uow).execute(uc.ReplacePricingCommand(Decimal(18), 0, Decimal(20), Decimal(5)))


def test_customer_levels_report_missing_and_complete_set(repo):
    uow = FakeUnitOfWork()
    replace = uc.ReplaceCustomerLevel(repo, uow)
    replace.execute(uc.ReplaceCustomerLevelCommand("a", Decimal(10), Decimal(25), 60))
    view = uc.ListCustomerLevels(repo, uow).execute()
    assert [r.level for r in view.rules] == [Level.A] and view.missing == (Level.B, Level.C)
    with pytest.raises(BusinessRuleError, match="Faltan configurar los niveles B, C"):
        uc.GetCompleteLevelRules(repo, uow).execute()
    for level in ("B", "C"):
        replace.execute(uc.ReplaceCustomerLevelCommand(level, Decimal(5), Decimal(20), 30))
    assert len(uc.GetCompleteLevelRules(repo, uow).execute().rules) == 3
    with pytest.raises(NotFoundError):
        replace.execute(uc.ReplaceCustomerLevelCommand("Z", Decimal(5), Decimal(20), 30))


def test_thresholds_and_classification(repo):
    uow = FakeUnitOfWork()
    with pytest.raises(NotFoundError):
        uc.ClassifyLevel(repo, uow).execute(Decimal(100))
    with pytest.raises(BusinessRuleError):
        uc.ReplaceLevelThresholds(repo, uow).execute(uc.ReplaceLevelThresholdsCommand(Decimal(5000), Decimal(1000)))
    uc.ReplaceLevelThresholds(repo, uow).execute(uc.ReplaceLevelThresholdsCommand(Decimal(10000), Decimal(50000)))
    assert uc.ClassifyLevel(repo, uow).execute(Decimal(60000)) is Level.A
    assert uc.ClassifyLevel(repo, uow).execute(Decimal(100)) is Level.C
