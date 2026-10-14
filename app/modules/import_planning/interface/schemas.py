"""Contrato de la simulación de importación."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.import_planning.infrastructure.orm import ImportLaboratoryRow, ImportSuggestionRow


class SuggestionOut(BaseModel):
    id: int
    product_name: str
    stock_units: int
    coverage_days: int
    demand_90_days: int
    suggested_units: int
    shelf_life_months: int
    order_before: date
    unit_price_usd: Decimal
    decision: Literal["pending", "approved", "rejected"]
    data_origin: Literal["simulated"] = "simulated"

    @classmethod
    def from_row(cls, row: ImportSuggestionRow, today: date) -> "SuggestionOut":
        return cls(id=row.id, product_name=row.product_name, stock_units=row.stock_units,
                   coverage_days=row.coverage_days, demand_90_days=row.demand_90_days,
                   suggested_units=row.suggested_units, shelf_life_months=row.shelf_life_months,
                   order_before=today + timedelta(days=row.days_until_order),
                   unit_price_usd=row.unit_price_usd, decision=row.decision)


class LaboratoryOut(BaseModel):
    id: int
    name: str
    country: str
    lead_days: int
    merchandise_cost_usd: Decimal
    import_cost_usd: int
    estimated_arrival: date
    data_origin: Literal["simulated"] = "simulated"
    suggestions: list[SuggestionOut]

    @classmethod
    def from_rows(cls, lab: ImportLaboratoryRow, rows: list[ImportSuggestionRow], today: date) -> "LaboratoryOut":
        return cls(id=lab.id, name=lab.name, country=lab.country, lead_days=lab.lead_days,
                   merchandise_cost_usd=sum((row.suggested_units * row.unit_price_usd for row in rows), Decimal(0)),
                   import_cost_usd=lab.import_cost_usd, estimated_arrival=today + timedelta(days=lab.lead_days),
                   suggestions=[SuggestionOut.from_row(row, today) for row in rows])


class ImportPlanOut(BaseModel):
    data_origin: Literal["simulated"] = "simulated"
    warning: str = Field(default="Escenario de ejemplo. Los laboratorios, productos, stock, demanda, precios, costos y fechas son simulados. No genera pedidos reales.")
    laboratories: list[LaboratoryOut]


class DecisionIn(BaseModel):
    decision: Literal["pending", "approved", "rejected"]
