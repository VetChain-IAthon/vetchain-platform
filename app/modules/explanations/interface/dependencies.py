"""Cableado de explanations: único lugar de la interfaz que ve la infraestructura.

Sin GEMINI_API_KEY se inyectan adaptadores que siempre fallan: las explicaciones usan el texto de reserva y las
preguntas responden `ai_unavailable`, sin romper el resto de la API.
"""
from datetime import date
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.modules.explanations.application import public
from app.modules.explanations.application import use_cases as uc
from app.modules.explanations.infrastructure.adapters import (
    FilePromptRepository,
    ReportsInsightQueryRunner,
    SqlCustomerNameSource,
    TemplateFallbackTextBuilder,
    latest_order_date,
)
from app.modules.explanations.infrastructure.gemini import (
    GeminiQueryPlanner,
    GeminiTextGenerator,
    UnavailableQueryPlanner,
    UnavailableTextGenerator,
    build_client,
)

_prompts = FilePromptRepository()


@lru_cache(maxsize=1)
def _client(api_key: str, timeout_seconds: int):
    return build_client(api_key, timeout_seconds)


def text_generator():
    if not settings.gemini_api_key:
        return UnavailableTextGenerator()
    return GeminiTextGenerator(_client(settings.gemini_api_key, settings.gemini_timeout_seconds), settings.gemini_model)


def query_planner(data_until: date | None = None):
    if not settings.gemini_api_key:
        return UnavailableQueryPlanner()
    return GeminiQueryPlanner(_client(settings.gemini_api_key, settings.gemini_timeout_seconds), settings.gemini_model,
                              _prompts, data_until=data_until)


def build_explain_alert() -> uc.ExplainAlert:
    return uc.ExplainAlert(_prompts, text_generator(), TemplateFallbackTextBuilder())


def get_ask_insight_question(db: Session = Depends(get_db)) -> uc.AskInsightQuestion:
    data_until = latest_order_date(db)
    return uc.AskInsightQuestion(query_planner(data_until), ReportsInsightQueryRunner(), text_generator(), _prompts,
                                 SqlCustomerNameSource(db), data_until)


public.configure(build_explain_alert)
