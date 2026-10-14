from decimal import Decimal

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.infrastructure.db.source_models import AMOUNT

PERCENT = Numeric(5, 2)
SINGLETON_ID = 1


class PricingSettingsRow(Base):
    """Una sola fila (id = 1)."""

    __tablename__ = "pricing_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    igv_rate_pct: Mapped[Decimal] = mapped_column(PERCENT)
    quotation_validity_days: Mapped[int] = mapped_column(Integer)
    min_margin_pct: Mapped[Decimal] = mapped_column(PERCENT)
    promo_margin_cut_pct: Mapped[Decimal] = mapped_column(PERCENT)


class CustomerLevelRow(Base):
    __tablename__ = "customer_levels"

    level: Mapped[str] = mapped_column(String(1), primary_key=True)
    max_discount_pct: Mapped[Decimal] = mapped_column(PERCENT)
    margin_pct: Mapped[Decimal] = mapped_column(PERCENT)
    credit_days: Mapped[int] = mapped_column(Integer)


class LevelThresholdsRow(Base):
    """Una sola fila (id = 1). Montos de pedidos en 12 meses, sin IGV."""

    __tablename__ = "level_thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    min_amount_b: Mapped[Decimal] = mapped_column(AMOUNT)
    min_amount_a: Mapped[Decimal] = mapped_column(AMOUNT)
