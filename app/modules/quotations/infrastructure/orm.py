from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QuotationRow(Base):
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20))
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    net: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    igv: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_with_tax: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    margin_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    approval_required: Mapped[bool]
    approval_reasons: Mapped[str] = mapped_column(Text)
    approval_confirmed: Mapped[bool]
    approval_note: Mapped[str | None] = mapped_column(Text)
    issued_on: Mapped[date] = mapped_column(Date, index=True)
    valid_until: Mapped[date] = mapped_column(Date)
    order_no: Mapped[str | None] = mapped_column(String(20))
    lines: Mapped[list["QuotationLineRow"]] = relationship(back_populates="quotation", cascade="all, delete-orphan", lazy="selectin")


class QuotationLineRow(Base):
    __tablename__ = "quotation_lines"

    quotation_id: Mapped[int] = mapped_column(ForeignKey("quotations.id"), primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code"), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    price_origin: Mapped[str] = mapped_column(String(20))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    quotation: Mapped[QuotationRow] = relationship(back_populates="lines")
