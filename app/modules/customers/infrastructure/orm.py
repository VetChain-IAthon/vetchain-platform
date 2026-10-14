from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContactRow(Base):
    """Registro de cada vez que alguien contacta a un cliente. Se completa (alert_id) al construir customers."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(String(30))  # 5 opciones por definir
    contact_date: Mapped[date]


class CustomerDiscardRow(Base):
    """Cliente dormido descartado (cerró, cambió de datos o no es viable). Vigente mientras restored_on sea nulo."""

    __tablename__ = "customer_discards"

    id: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    reason: Mapped[str] = mapped_column(String(30))  # business_closed | data_changed | not_viable | other
    note: Mapped[str | None] = mapped_column(String(300))
    discarded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    discarded_on: Mapped[date]
    restored_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    restored_on: Mapped[date | None]
