from pydantic import BaseModel, Field

from app.core.schemas import JsonNumber

from app.modules.settings.domain.entities import CustomerLevelRule, LevelThresholds, PricingSettings



class PricingIn(BaseModel):
    igv_rate_pct: JsonNumber = Field(ge=0, le=100, examples=[18])
    quotation_validity_days: int = Field(ge=1, examples=[15])
    min_margin_pct: JsonNumber = Field(ge=0, le=100)
    promo_margin_cut_pct: JsonNumber = Field(ge=0, le=100, description="Cuánto baja el margen mínimo en promociones")


class PricingOut(PricingIn):
    @classmethod
    def from_domain(cls, pricing: PricingSettings) -> "PricingOut":
        return cls(
            igv_rate_pct=pricing.igv_rate.value,
            quotation_validity_days=pricing.quotation_validity_days,
            min_margin_pct=pricing.min_margin.value,
            promo_margin_cut_pct=pricing.promo_margin_cut.value,
        )


class CustomerLevelIn(BaseModel):
    max_discount_pct: JsonNumber = Field(ge=0, le=100)
    margin_pct: JsonNumber = Field(ge=0, le=100)
    credit_days: int = Field(ge=0)


class CustomerLevelOut(CustomerLevelIn):
    level: str

    @classmethod
    def from_domain(cls, rule: CustomerLevelRule) -> "CustomerLevelOut":
        return cls(
            level=rule.level.value,
            max_discount_pct=rule.max_discount.value,
            margin_pct=rule.margin.value,
            credit_days=rule.credit_days,
        )


class CustomerLevelsOut(BaseModel):
    items: list[CustomerLevelOut]
    missing_levels: list[str] = Field(description="Niveles que gerencia aún no configuró")


class LevelThresholdsIn(BaseModel):
    min_amount_b: JsonNumber = Field(ge=0, description="Monto mínimo de pedidos en 12 meses (PEN, sin IGV) para ser B")
    min_amount_a: JsonNumber = Field(ge=0, description="Monto mínimo para ser A; debe ser mayor o igual que el de B")


class LevelThresholdsOut(LevelThresholdsIn):
    @classmethod
    def from_domain(cls, thresholds: LevelThresholds) -> "LevelThresholdsOut":
        return cls(min_amount_b=thresholds.min_amount_b.amount, min_amount_a=thresholds.min_amount_a.amount)
