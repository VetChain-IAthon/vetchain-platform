from dataclasses import dataclass
from enum import StrEnum

from app.core.domain import BusinessRuleError, Money, Percentage


class Level(StrEnum):
    A = "A"
    B = "B"
    C = "C"


@dataclass(frozen=True)
class PricingSettings:
    igv_rate: Percentage
    quotation_validity_days: int
    min_margin: Percentage
    promo_margin_cut: Percentage

    def __post_init__(self) -> None:
        if self.quotation_validity_days < 1:
            raise BusinessRuleError("La vigencia de la cotización debe ser de al menos 1 día.", "invalid_validity_days")


@dataclass(frozen=True)
class CustomerLevelRule:
    level: Level
    max_discount: Percentage
    margin: Percentage
    credit_days: int

    def __post_init__(self) -> None:
        if self.credit_days < 0:
            raise BusinessRuleError("Los días de crédito no pueden ser negativos.", "invalid_credit_days")


@dataclass(frozen=True)
class LevelRules:
    """Las reglas de los tres niveles. Siempre existen A, B y C."""

    rules: tuple[CustomerLevelRule, ...]

    def __post_init__(self) -> None:
        levels = [rule.level for rule in self.rules]
        if sorted(levels) != sorted(Level):
            raise BusinessRuleError("Deben existir exactamente los niveles A, B y C.", "invalid_level_rules")
        object.__setattr__(self, "rules", tuple(sorted(self.rules, key=lambda rule: rule.level)))

    def for_level(self, level: Level) -> CustomerLevelRule:
        return next(rule for rule in self.rules if rule.level is level)

    def replace(self, new_rule: CustomerLevelRule) -> "LevelRules":
        return LevelRules(tuple(new_rule if rule.level is new_rule.level else rule for rule in self.rules))


@dataclass(frozen=True)
class LevelThresholds:
    """Monto mínimo de pedidos en 12 meses para ser B y para ser A."""

    min_amount_b: Money
    min_amount_a: Money

    def __post_init__(self) -> None:
        if self.min_amount_b.is_negative:
            raise BusinessRuleError("Los umbrales no pueden ser negativos.", "invalid_thresholds")
        if self.min_amount_a < self.min_amount_b:
            raise BusinessRuleError("El umbral de A debe ser mayor o igual que el de B.", "invalid_thresholds")
