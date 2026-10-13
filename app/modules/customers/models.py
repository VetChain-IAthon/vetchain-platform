from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Contact(Base):
    """Registro de cada vez que alguien contacta a un cliente."""
    __tablename__ = "contacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(String(30))  # 5 opciones por definir
    contact_date: Mapped[date]
