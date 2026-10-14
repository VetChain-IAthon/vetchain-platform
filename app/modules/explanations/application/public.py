"""Fachada de explanations para otros módulos (hoy, customers). Solo tipos simples.

Recibe `AlertFiguresInput`, un DTO propio, para que customers no importe el dominio de explanations
(punto abierto 2 de docs/capas.md). La interfaz registra al cargarse cómo construir el caso de uso (`configure`).
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from app.core.domain import Money
from app.modules.explanations.application.use_cases import ExplainAlert
from app.modules.explanations.domain.entities import AggregatedFigures

_factory: Callable[[], ExplainAlert] | None = None


def configure(factory: Callable[[], ExplainAlert]) -> None:
    global _factory
    _factory = factory


@dataclass(frozen=True)
class AlertFiguresInput:
    """Cifras agregadas de una alerta. No lleva nombre ni RUC."""

    days_since_last_purchase: int
    purchase_frequency_days: Decimal | None
    repurchase_probability: Decimal  # 0 a 1, viene del modelo de predicción
    average_order_amount: Decimal
    top_families: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AlertExplanationResult:
    text: str
    source: str  # ai | fallback


def explain_alert(figures: AlertFiguresInput) -> AlertExplanationResult:
    if _factory is None:
        raise RuntimeError("explanations no está configurado: falta importar app.modules.explanations.interface.")
    explanation = _factory().execute(AggregatedFigures(
        figures.days_since_last_purchase, figures.purchase_frequency_days, figures.repurchase_probability,
        Money(figures.average_order_amount), figures.top_families,
    ))
    return AlertExplanationResult(explanation.text, explanation.source.value)
