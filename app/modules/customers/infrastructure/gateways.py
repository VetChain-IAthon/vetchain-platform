"""Adaptadores hacia otros módulos (anticorrupción): llaman solo a su application/public.py."""
from app.core.domain import BusinessRuleError, Money, Percentage
from app.modules.customers.domain.value_objects import CommercialTerms, Level, LevelThresholds
import app.modules.settings.application.public as settings_public


class SettingsPublicGateway:
    """Implementa SettingsGateway con la fachada de settings."""

    def level_thresholds(self) -> LevelThresholds | None:
        thresholds = settings_public.get_level_thresholds()
        if thresholds is None:
            return None
        return LevelThresholds(Money(thresholds.min_amount_b), Money(thresholds.min_amount_a))

    def commercial_terms(self, level: Level) -> CommercialTerms:
        rule = next((r for r in settings_public.get_level_rules() if r.level == level.value), None)
        if rule is None:  # get_level_rules ya exige A, B y C; esto es una defensa
            raise BusinessRuleError(f"Falta configurar el nivel {level.value} en Ajustes.", "levels_not_configured")
        return CommercialTerms(level, Percentage(rule.margin_pct), Percentage(rule.max_discount_pct), rule.credit_days)
