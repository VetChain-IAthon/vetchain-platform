from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomerTier(Base):
    """Nivel de cliente (A, B, C) con sus límites comerciales."""
    __tablename__ = "customer_tiers"
    tier: Mapped[str] = mapped_column(String(1), primary_key=True)
    max_discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    margin_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    credit_days: Mapped[int]


class CustomerRebate(Base):
    __tablename__ = "customer_rebates"
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), primary_key=True)
    rebate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
