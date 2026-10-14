"""Prompts en archivo, texto de reserva, consultas vía reports y nombres de clientes para PrivacyGuard."""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.modules.reports.application.public as reports_public
from app.core.domain import DataOrigin
from app.infrastructure.db.source_models import Customer
from app.modules.explanations.domain.entities import AggregatedFigures, AggregatedResult, InsightQuery

PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts"


class FilePromptRepository:
    """Implementa PromptRepository: lee prompts/<name>.md."""

    def __init__(self, directory: Path = PROMPTS_DIR) -> None:
        self._directory = directory

    def get(self, name: str) -> str:
        return (self._directory / f"{name}.md").read_text(encoding="utf-8")


class TemplateFallbackTextBuilder:
    """Implementa FallbackTextBuilder: texto fijo con las mismas cifras, para cuando la IA no responde."""

    def build(self, figures: AggregatedFigures) -> str:
        values = figures.as_prompt_values()
        text = (f"Lleva {values['days_since_last_purchase']} días sin comprar"
                + (f" y suele comprar cada {values['purchase_frequency_days']} días"
                   if figures.purchase_frequency_days is not None else "")
                + f". Probabilidad de recompra: {values['repurchase_probability_pct']} %."
                + f" Pedido promedio: S/ {values['avg_order_amount']}.")
        if figures.top_families:
            text += f" Compra sobre todo {values['top_families']}."
        return text


class ReportsInsightQueryRunner:
    """Implementa InsightQueryRunner con la fachada pública de reports."""

    def run(self, query: InsightQuery) -> AggregatedResult:
        result = reports_public.run_allowed_query(
            query.query_type.value,
            query.date_range.from_date if query.date_range else None,
            query.date_range.to_date if query.date_range else None,
            dict(query.filters),
        )
        return AggregatedResult(tuple(result.rows), tuple(result.sources), DataOrigin(result.data_origin))


class SqlCustomerNameSource:
    """Implementa CustomerNameSource leyendo la tabla customers (solo lectura)."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def names(self) -> frozenset[str]:
        return frozenset(self._db.scalars(select(Customer.name)).all())
