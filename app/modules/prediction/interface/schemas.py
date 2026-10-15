"""Salida pública de la comparación de pronósticos."""
from pydantic import BaseModel, Field


class ForecastComparisonOut(BaseModel):
    product_id: str
    scenario: str = Field(description="A: cantidad solicitada T/A; B: la misma cantidad con precio unitario positivo.")
    horizon_months: int
    cutoff_month: str
    forecast_start_month: str
    moving_average_6m: float = Field(description="Cantidad total estimada para el horizonte.")
    extra_trees: float = Field(description="Cantidad total estimada para el horizonte.")
    data_origin: str
    warning: str


class ForecastExplanationIn(BaseModel):
    product_id: str = Field(min_length=1)
    scenario: str = Field(default="A", pattern="^(A|B)$")
    horizon: int = Field(default=1, ge=1, le=3)
    cutoff: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class ForecastExplanationOut(BaseModel):
    text: str
    source: str = Field(description="gemini si la IA redactó el texto; fallback si se usó una plantilla.")
