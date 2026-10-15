"""Secciones simuladas: una fila por bloque de pantalla (`receivables`, `kpis`, `tiles`…), con su contenido en JSON.

Separadas de las tablas importadas de Defontana. Se cargan por migración y se reemplazan cuando llegue el dato real.
"""
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SimulatedSectionRow(Base):
    __tablename__ = "simulated_sections"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="simulated")
