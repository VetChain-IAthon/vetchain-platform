from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.domain import Money, Percentage
from app.modules.settings.domain.entities import CustomerLevelRule, Level, LevelThresholds, PricingSettings
from app.modules.settings.infrastructure.orm import (
    SINGLETON_ID,
    CustomerLevelRow,
    LevelThresholdsRow,
    PricingSettingsRow,
)


class SqlAlchemySettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_pricing(self) -> PricingSettings | None:
        row = self._session.get(PricingSettingsRow, SINGLETON_ID)
        if row is None:
            return None
        return PricingSettings(
            Percentage(row.igv_rate_pct), row.quotation_validity_days,
            Percentage(row.min_margin_pct), Percentage(row.promo_margin_cut_pct),
        )

    def save_pricing(self, pricing: PricingSettings) -> None:
        row = self._session.get(PricingSettingsRow, SINGLETON_ID) or PricingSettingsRow(id=SINGLETON_ID)
        row.igv_rate_pct = pricing.igv_rate.value
        row.quotation_validity_days = pricing.quotation_validity_days
        row.min_margin_pct = pricing.min_margin.value
        row.promo_margin_cut_pct = pricing.promo_margin_cut.value
        self._session.add(row)
        self._session.flush()

    def list_level_rules(self) -> list[CustomerLevelRule]:
        rows = self._session.scalars(select(CustomerLevelRow).order_by(CustomerLevelRow.level))
        return [
            CustomerLevelRule(Level(row.level), Percentage(row.max_discount_pct), Percentage(row.margin_pct), row.credit_days)
            for row in rows
        ]

    def save_level_rule(self, rule: CustomerLevelRule) -> None:
        row = self._session.get(CustomerLevelRow, rule.level.value) or CustomerLevelRow(level=rule.level.value)
        row.max_discount_pct = rule.max_discount.value
        row.margin_pct = rule.margin.value
        row.credit_days = rule.credit_days
        self._session.add(row)
        self._session.flush()

    def get_thresholds(self) -> LevelThresholds | None:
        row = self._session.get(LevelThresholdsRow, SINGLETON_ID)
        return None if row is None else LevelThresholds(Money(row.min_amount_b), Money(row.min_amount_a))

    def save_thresholds(self, thresholds: LevelThresholds) -> None:
        row = self._session.get(LevelThresholdsRow, SINGLETON_ID) or LevelThresholdsRow(id=SINGLETON_ID)
        row.min_amount_b = thresholds.min_amount_b.amount
        row.min_amount_a = thresholds.min_amount_a.amount
        self._session.add(row)
        self._session.flush()
