"""Escenario de demostración; separado de las tablas importadas de Defontana."""
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportLaboratoryRow(Base):
    __tablename__ = "import_laboratories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False)
    lead_days: Mapped[int] = mapped_column(Integer, nullable=False)
    import_cost_usd: Mapped[int] = mapped_column(Integer, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ImportSuggestionRow(Base):
    __tablename__ = "import_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    laboratory_id: Mapped[int] = mapped_column(ForeignKey("import_laboratories.id"), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(150), nullable=False)
    stock_units: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_days: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_90_days: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_units: Mapped[int] = mapped_column(Integer, nullable=False)
    shelf_life_months: Mapped[int] = mapped_column(Integer, nullable=False)
    days_until_order: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
