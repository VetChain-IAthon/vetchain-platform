"""Adaptadores hacia otros módulos (anticorrupción): llaman solo a su application/public.py."""
from app.core.domain import BusinessRuleError, Money, Percentage
from app.modules.customers.domain.entities import AlertExplanation, AlertFigures
from app.modules.customers.domain.value_objects import CommercialTerms, Level, LevelThresholds
import app.modules.auth.application.public as auth_public
import app.modules.explanations.application.public as explanations_public
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


class ExplanationPublicGateway:
    """Implementa ExplanationGateway con la fachada de explanations. Listo para cuando existan las alertas."""

    def explain(self, figures: AlertFigures) -> AlertExplanation:
        result = explanations_public.explain_alert(explanations_public.AlertFiguresInput(
            figures.days_since_last_order, figures.purchase_frequency_days, figures.repurchase_probability.value,
            figures.average_order_amount.amount, figures.top_families,
        ))
        return AlertExplanation(result.text, result.source)


class UserDirectoryPublicGateway:
    """Implementa UserDirectoryGateway con la fachada de auth."""

    def names(self, user_ids: list[int]) -> dict[int, str]:
        return auth_public.user_names(user_ids)
