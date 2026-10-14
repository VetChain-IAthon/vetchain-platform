"""Casos de uso de settings: reglas del negocio que configura gerencia."""
from dataclasses import dataclass
from decimal import Decimal

from app.core.domain import BusinessRuleError, Money, NotFoundError, Percentage, UnitOfWork
from app.modules.settings.domain.entities import (
    CustomerLevelRule,
    Level,
    LevelRules,
    LevelThresholds,
    PricingSettings,
    missing_levels,
)
from app.modules.settings.domain.ports import SettingsRepository
from app.modules.settings.domain.services import LevelPolicy


def _level(value: str) -> Level:
    try:
        return Level(value.upper())
    except ValueError:
        raise NotFoundError(f"No existe el nivel {value}. Los niveles son A, B y C.", "level_not_found") from None


@dataclass(frozen=True)
class ReplacePricingCommand:
    igv_rate_pct: Decimal
    quotation_validity_days: int
    min_margin_pct: Decimal
    promo_margin_cut_pct: Decimal


@dataclass(frozen=True)
class ReplaceCustomerLevelCommand:
    level: str
    max_discount_pct: Decimal
    margin_pct: Decimal
    credit_days: int


@dataclass(frozen=True)
class ReplaceLevelThresholdsCommand:
    min_amount_b: Decimal
    min_amount_a: Decimal


@dataclass(frozen=True)
class CustomerLevelsView:
    rules: tuple[CustomerLevelRule, ...]
    missing: tuple[Level, ...]


class GetPricing:
    def __init__(self, repository: SettingsRepository, uow: UnitOfWork) -> None:
        self.repository, self.uow = repository, uow

    def execute(self) -> PricingSettings:
        with self.uow:
            pricing = self.repository.get_pricing()
            if pricing is None:
                raise NotFoundError("Las reglas de precios aún no están configuradas.", "pricing_not_configured")
            return pricing


class ReplacePricing:
    def __init__(self, repository: SettingsRepository, uow: UnitOfWork) -> None:
        self.repository, self.uow = repository, uow

    def execute(self, command: ReplacePricingCommand) -> PricingSettings:
        with self.uow:
            pricing = PricingSettings(
                igv_rate=Percentage(command.igv_rate_pct),
                quotation_validity_days=command.quotation_validity_days,
                min_margin=Percentage(command.min_margin_pct),
                promo_margin_cut=Percentage(command.promo_margin_cut_pct),
            )
            self.repository.save_pricing(pricing)
            self.uow.commit()
            return pricing


class ListCustomerLevels:
    def __init__(self, repository: SettingsRepository, uow: UnitOfWork) -> None:
        self.repository, self.uow = repository, uow

    def execute(self) -> CustomerLevelsView:
        with self.uow:
            rules = sorted(self.repository.list_level_rules(), key=lambda rule: rule.level)
            return CustomerLevelsView(tuple(rules), missing_levels(rules))


class ReplaceCustomerLevel:
    def __init__(self, repository: SettingsRepository, uow: UnitOfWork) -> None:
        self.repository, self.uow = repository, uow

    def execute(self, command: ReplaceCustomerLevelCommand) -> CustomerLevelRule:
        with self.uow:
            rule = CustomerLevelRule(
                level=_level(command.level),
                max_discount=Percentage(command.max_discount_pct),
                margin=Percentage(command.margin_pct),
                credit_days=command.credit_days,
            )
            self.repository.save_level_rule(rule)
            self.uow.commit()
            return rule


class GetLevelThresholds:
    def __init__(self, repository: SettingsRepository, uow: UnitOfWork) -> None:
        self.repository, self.uow = repository, uow

    def execute(self) -> LevelThresholds:
        with self.uow:
            thresholds = self.repository.get_thresholds()
            if thresholds is None:
                raise NotFoundError("Los umbrales de nivel aún no están configurados.", "thresholds_not_configured")
            return thresholds


class ReplaceLevelThresholds:
    def __init__(self, repository: SettingsRepository, uow: UnitOfWork) -> None:
        self.repository, self.uow = repository, uow

    def execute(self, command: ReplaceLevelThresholdsCommand) -> LevelThresholds:
        with self.uow:
            thresholds = LevelThresholds(Money(command.min_amount_b), Money(command.min_amount_a))
            self.repository.save_thresholds(thresholds)
            self.uow.commit()
            return thresholds


class GetCompleteLevelRules:
    """Para otros módulos: las reglas de A, B y C. BusinessRuleError si falta configurar alguno."""

    def __init__(self, repository: SettingsRepository, uow: UnitOfWork) -> None:
        self.repository, self.uow = repository, uow

    def execute(self) -> LevelRules:
        with self.uow:
            rules = self.repository.list_level_rules()
            missing = missing_levels(rules)
            if missing:
                raise BusinessRuleError(
                    f"Faltan configurar los niveles {', '.join(missing)} en Ajustes.", "levels_not_configured"
                )
            return LevelRules(tuple(rules))


class ClassifyLevel:
    def __init__(self, repository: SettingsRepository, uow: UnitOfWork) -> None:
        self.repository, self.uow = repository, uow

    def execute(self, amount_12m: Decimal) -> Level:
        thresholds = GetLevelThresholds(self.repository, self.uow).execute()
        return LevelPolicy(thresholds).classify(Money(amount_12m))
