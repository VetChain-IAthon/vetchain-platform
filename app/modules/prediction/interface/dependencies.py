"""Cableado del caso de uso de pronóstico."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.prediction.application.use_cases import CompareForecasts, ExplainForecast
from app.modules.prediction.infrastructure.forecast import PrivateExtraTreesModel, SqlForecastHistoryReader
from app.modules.prediction.infrastructure.gemini import GeminiForecastTextGenerator


def get_compare_forecasts(db: Session = Depends(get_db)) -> CompareForecasts:
    return CompareForecasts(SqlForecastHistoryReader(db), PrivateExtraTreesModel(settings.forecast_models_dir))


def get_explain_forecast(forecasts: CompareForecasts = Depends(get_compare_forecasts)) -> ExplainForecast:
    return ExplainForecast(forecasts, GeminiForecastTextGenerator(
        settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout_seconds))
