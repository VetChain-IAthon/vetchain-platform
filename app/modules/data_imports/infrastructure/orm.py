from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataImportRow(Base):
    """Cada CSV subido desde Ajustes. `staged_rows` guarda las filas (JSON) mientras la carga está en revisión."""

    __tablename__ = "data_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(20), index=True)
    origin: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    file_name: Mapped[str] = mapped_column(String(200))
    rows_read: Mapped[int] = mapped_column(Integer)
    rows_with_error: Mapped[int] = mapped_column(Integer)
    rows_loaded: Mapped[int | None] = mapped_column(Integer)
    errors: Mapped[str] = mapped_column(Text)  # JSON: [[línea, mensaje], ...]
    staged_rows: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
