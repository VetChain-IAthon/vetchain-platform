"""Pronóstico de cantidades registradas, con promedio móvil y Extra Trees."""
from dataclasses import dataclass
from datetime import date, timedelta
from math import isfinite
import logging
from statistics import mean, stdev

from app.core.domain import BusinessRuleError, NotFoundError
from app.modules.prediction.domain.entities import MonthlyDemand
from app.modules.prediction.domain.ports import ForecastHistoryReader, ForecastModel, ForecastTextGenerator

logger = logging.getLogger(__name__)


def _month_number(value: date) -> int:
    return value.year * 12 + value.month - 1


def _month_from_number(number: int) -> date:
    return date(number // 12, number % 12 + 1, 1)


@dataclass(frozen=True)
class ForecastComparison:
    product_id: str
    scenario: str
    horizon_months: int
    cutoff_month: str
    forecast_start_month: str
    moving_average_6m: float
    extra_trees: float
    data_origin: str = "estimated"
    warning: str = (
        "Son estimaciones de cantidades solicitadas en pedidos, no ventas facturadas "
        "ni una recomendación automática de importación."
    )


class CompareForecasts:
    def __init__(self, history: ForecastHistoryReader, model: ForecastModel) -> None:
        self.history = history
        self.model = model

    def execute(self, product_id: str, scenario: str, horizon: int, cutoff: date | None) -> ForecastComparison:
        if scenario not in ("A", "B") or horizon not in (1, 3):
            raise BusinessRuleError("El escenario o el horizonte no es válido.", "invalid_forecast_request")
        latest = self.history.latest_order_date()
        if latest is None:
            raise NotFoundError("No hay pedidos para calcular pronósticos.", "forecast_history_not_found")
        last_complete_month = latest.replace(day=1) - timedelta(days=1)
        if cutoff is None:
            cutoff = latest.replace(day=1) - timedelta(days=1)
        cutoff_month = cutoff.replace(day=1)
        if cutoff_month > last_complete_month:
            raise BusinessRuleError("El corte debe ser un mes cerrado anterior al último pedido registrado.", "invalid_forecast_cutoff")
        first_month = self.history.first_month(product_id)
        if first_month is None or first_month > cutoff_month:
            raise NotFoundError("El producto no tiene historial de pedidos válido.", "forecast_history_not_found")
        rows = self.history.monthly_history(product_id, scenario, cutoff_month)
        first = _month_number(first_month)
        target = _month_number(cutoff_month) + 1
        quantities = { _month_number(row.month): float(row.quantity) for row in rows }
        history = [quantities.get(month, 0.0) for month in range(first, target)]
        if len(history) < 12:
            raise BusinessRuleError("Se necesitan al menos 12 meses de historial.", "insufficient_forecast_history")
        if any(not isfinite(value) or value < 0 for value in history):
            raise BusinessRuleError("El historial contiene cantidades inválidas.", "invalid_forecast_history")
        prefix = f"{scenario}_"
        features: dict[str, str | int | float] = {
            "producto_id": product_id,
            "mes_num": _month_from_number(target).month,
            "meses_historicos_disponibles": len(history),
            **{f"{prefix}lag_{lag}m": history[-lag] for lag in (1, 2, 3, 6, 12)},
            **{f"{prefix}promedio_{span}m": mean(history[-span:]) for span in (3, 6, 12)},
            f"{prefix}std_3m": stdev(history[-3:]),
        }
        extra_trees = self.model.predict(scenario, horizon, features)
        if not isfinite(extra_trees) or extra_trees < 0:
            raise BusinessRuleError("El modelo devolvió una cantidad inválida.", "invalid_model_output")
        return ForecastComparison(
            product_id=product_id,
            scenario=scenario,
            horizon_months=horizon,
            cutoff_month=cutoff_month.strftime("%Y-%m"),
            forecast_start_month=_month_from_number(target).strftime("%Y-%m"),
            moving_average_6m=round(mean(history[-6:]) * horizon, 2),
            extra_trees=round(extra_trees, 2),
        )


@dataclass(frozen=True)
class ForecastExplanation:
    text: str
    source: str  # gemini | fallback


class ExplainForecast:
    """Explica cifras calculadas; la IA no decide ni modifica el pronóstico."""

    def __init__(self, forecasts: CompareForecasts, generator: ForecastTextGenerator) -> None:
        self.forecasts = forecasts
        self.generator = generator

    def execute(self, product_id: str, scenario: str, horizon: int, cutoff: date | None) -> ForecastExplanation:
        result = self.forecasts.execute(product_id, scenario, horizon, cutoff)
        prompt = (
            "Explica en español claro, en dos frases, estos pronósticos de cantidades solicitadas "
            "en pedidos veterinarios. Usa solo las cifras dadas. No inventes causas, porcentajes, "
            "intervalos, ventas facturadas ni recomendaciones de compra o importación. "
            "No menciones nombres de algoritmos, modelos ni proveedores de IA. "
            + ("Aclara que son estimaciones y que la cantidad de tres meses es acumulada. " if result.horizon_months == 3
               else "Aclara que son estimaciones. ")
            + f"Escenario: {result.scenario}. Corte: {result.cutoff_month}. "
            f"Horizonte: {result.horizon_months} mes(es). "
            f"Promedio móvil de 6 meses: {result.moving_average_6m}. "
            f"Modelo predictivo: {result.extra_trees}."
        )
        try:
            text = self.generator.generate(prompt).strip()
            if text:
                return ForecastExplanation(text, "gemini")
        except Exception as exc:
            logger.warning("Gemini no pudo explicar el pronóstico; se usa texto de respaldo (%s).", type(exc).__name__)
        return ForecastExplanation(
            f"Para {result.horizon_months} {'mes' if result.horizon_months == 1 else 'meses acumulados'}, el promedio móvil estima "
            f"{result.moving_average_6m} y el modelo predictivo estima {result.extra_trees} "
            "en cantidades solicitadas. Son estimaciones; no equivalen a ventas facturadas "
            "ni indican cuánto importar.",
            "fallback",
        )
