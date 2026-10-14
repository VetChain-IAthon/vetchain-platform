from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.source_tables import PEN


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    total: Mapped[Decimal] = mapped_column(PEN, default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class QuoteLine(Base):
    __tablename__ = "quote_lines"
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code"), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal] = mapped_column(PEN)
