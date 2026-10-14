"""Fachada de settings para otros módulos. Solo tipos simples (Decimal, int, str).

La interfaz de settings registra al cargarse cómo abrir el repositorio y la unidad de trabajo (`configure`).
"""
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from decimal import Decimal

from app.core.domain import NotFoundError, UnitOfWork
from app.modules.settings.application.use_cases import ClassifyLevel, GetCompleteLevelRules, GetLevelThresholds, GetPricing
from app.modules.settings.domain.ports import SettingsRepository

Scope = Callable[[], AbstractContextManager[tuple[SettingsRepository, UnitOfWork]]]
_scope: Scope | None = None


def configure(scope: Scope) -> None:
    global _scope
    _scope = scope


@dataclass(frozen=True)
class PricingTerms:
    igv_rate_pct: Decimal
    quotation_validity_days: int
    min_margin_pct: Decimal
    promo_margin_cut_pct: Decimal


@dataclass(frozen=True)
class LevelRule:
    level: str
    max_discount_pct: Decimal
    margin_pct: Decimal
    credit_days: int


@dataclass(frozen=True)
class Thresholds:
    min_amount_b: Decimal
    min_amount_a: Decimal


def _open():
    if _scope is None:
        raise RuntimeError("settings no está configurado: falta importar app.modules.settings.interface.")
    return _scope()


def get_pricing() -> PricingTerms:
    with _open() as (repository, uow):
        pricing = GetPricing(repository, uow).execute()
    return PricingTerms(
        pricing.igv_rate.value, pricing.quotation_validity_days, pricing.min_margin.value, pricing.promo_margin_cut.value
    )


def get_level_rules() -> list[LevelRule]:
    with _open() as (repository, uow):
        rules = GetCompleteLevelRules(repository, uow).execute()
    return [
        LevelRule(rule.level.value, rule.max_discount.value, rule.margin.value, rule.credit_days) for rule in rules.rules
    ]


def get_level_thresholds() -> Thresholds | None:
    """Umbrales de nivel, o None mientras gerencia no los defina."""
    with _open() as (repository, uow):
        try:
            thresholds = GetLevelThresholds(repository, uow).execute()
        except NotFoundError:
            return None
    return Thresholds(thresholds.min_amount_b.amount, thresholds.min_amount_a.amount)


def classify_level(amount_12m: Decimal) -> str:
    with _open() as (repository, uow):
        return ClassifyLevel(repository, uow).execute(amount_12m).value
