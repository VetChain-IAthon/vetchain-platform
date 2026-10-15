from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.application import MANAGER
from app.core.auth import require_role
from app.core.errors import error_body
from app.core.stubs import add_pending_route
from app.modules.prediction.application.use_cases import CompareForecasts, ExplainForecast
from app.modules.prediction.interface.dependencies import get_compare_forecasts, get_explain_forecast
from app.modules.prediction.interface.schemas import ForecastComparisonOut, ForecastExplanationIn, ForecastExplanationOut

router = APIRouter(tags=["predicción"])
M = (MANAGER,)


def _parse_cutoff(cutoff: str | None) -> date | None:
    try:
        return date.fromisoformat(f"{cutoff}-01") if cutoff else None
    except ValueError as exc:
        raise HTTPException(422, error_body("validation_error", "El mes de corte no es válido.")) from exc

# Rutas del contrato (docs/endpoints.md). Se reemplazan por rutas reales al construir el módulo.
for method, path, roles, summary in [
    ("GET", "/prediction/model", M, "Versión, fecha de entrenamiento y calidad del modelo"),
]:
    add_pending_route(router, method, path, roles, summary)


@router.get("/prediction/forecasts", dependencies=[Depends(require_role(MANAGER))], response_model=ForecastComparisonOut)
def compare_forecasts(
    product_id: str = Query(min_length=1),
    scenario: str = Query(default="A", pattern="^(A|B)$"),
    horizon: int = Query(default=1),
    cutoff: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    use_case: CompareForecasts = Depends(get_compare_forecasts),
):
    """Compara Extra Trees con el promedio móvil para cantidades registradas."""
    if horizon not in (1, 3):
        raise HTTPException(422, error_body("validation_error", "El horizonte debe ser 1 o 3 meses."))
    cutoff_date = _parse_cutoff(cutoff)
    try:
        return use_case.execute(product_id.strip(), scenario, horizon, cutoff_date)
    except (FileNotFoundError, OSError, ValueError, ImportError) as exc:
        raise HTTPException(503, error_body("forecast_unavailable", f"Pronóstico no disponible: {exc}")) from exc


@router.post("/prediction/forecasts/explanation", dependencies=[Depends(require_role(MANAGER))], response_model=ForecastExplanationOut)
def explain_forecast(payload: ForecastExplanationIn, use_case: ExplainForecast = Depends(get_explain_forecast)):
    """Redacta una explicación con Gemini sobre las cifras del pronóstico calculado."""
    if payload.horizon not in (1, 3):
        raise HTTPException(422, error_body("validation_error", "El horizonte debe ser 1 o 3 meses."))
    cutoff_date = _parse_cutoff(payload.cutoff)
    try:
        return use_case.execute(payload.product_id.strip(), payload.scenario, payload.horizon, cutoff_date)
    except (FileNotFoundError, OSError, ValueError, ImportError) as exc:
        raise HTTPException(503, error_body("forecast_unavailable", f"Pronóstico no disponible: {exc}")) from exc
