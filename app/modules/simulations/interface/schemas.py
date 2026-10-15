"""Salida de las secciones simuladas."""
from typing import Any

from pydantic import BaseModel, Field


class SimulatedSectionsOut(BaseModel):
    origin: str = Field(default="simulated", description="Siempre `simulated`: cifras de ejemplo, no datos de Mederi.")
    sections: dict[str, Any] = Field(description="Bloques por clave (tiles, sections, receivables, salespeople, kpis, sales).")
