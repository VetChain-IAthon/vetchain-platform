"""Adaptadores de Gemini (google-genai). Solo reciben prompts ya armados con cifras agregadas."""
import json
from datetime import date

from google import genai
from google.genai import types

from app.core.domain import BusinessRuleError, DateRange
from app.modules.explanations.domain.entities import ALLOWED_FILTERS, AllowedQueryType, InsightQuery
from app.modules.explanations.domain.ports import PromptRepository

UNSUPPORTED = "unsupported"


class GeminiUnavailableError(RuntimeError):
    """Sin GEMINI_API_KEY. Los casos de uso lo tratan como cualquier fallo de la IA."""


def build_client(api_key: str, timeout_seconds: int) -> genai.Client:
    """En la capa gratuita Gemini responde 503 (alta demanda) o 504 a ratos: se reintenta antes de usar la reserva."""
    retry = types.HttpRetryOptions(attempts=3, initial_delay=1, max_delay=4, http_status_codes=[429, 500, 503, 504])
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000, retry_options=retry))


class GeminiTextGenerator:
    """Implementa TextGenerator."""

    def __init__(self, client: genai.Client, model: str) -> None:
        self._client, self._model = client, model

    def generate(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model, contents=prompt, config=types.GenerateContentConfig(temperature=0.3))
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini devolvió una respuesta vacía.")
        return text


class GeminiQueryPlanner:
    """Implementa QueryPlanner con salida estructurada: Gemini solo puede elegir un tipo de la lista cerrada."""

    def __init__(self, client: genai.Client, model: str, prompts: PromptRepository, today: date | None = None) -> None:
        self._client, self._model, self._prompts, self._today = client, model, prompts, today

    def plan(self, question: str, allowed: tuple[AllowedQueryType, ...]) -> InsightQuery | None:
        prompt = self._prompts.get("insight_planner").format(
            today=(self._today or date.today()).isoformat(), question=question)
        response = self._client.models.generate_content(
            model=self._model, contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json", response_json_schema=_schema(allowed)),
        )
        return parse_plan(response.text or "", allowed)


def _schema(allowed: tuple[AllowedQueryType, ...]) -> dict:
    return {
        "type": "object",
        "properties": {
            "query_type": {"type": "string", "enum": [t.value for t in allowed] + [UNSUPPORTED]},
            "date_from": {"type": "string", "description": "AAAA-MM-DD, o vacío si la pregunta no indica fechas"},
            "date_to": {"type": "string", "description": "AAAA-MM-DD, o vacío si la pregunta no indica fechas"},
            "filters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"key": {"type": "string", "enum": sorted(ALLOWED_FILTERS)}, "value": {"type": "string"}},
                    "required": ["key", "value"],
                },
            },
        },
        "required": ["query_type"],
    }


def parse_plan(raw: str, allowed: tuple[AllowedQueryType, ...]) -> InsightQuery | None:
    """Valida la respuesta de Gemini. Cualquier cosa fuera de la lista cerrada se trata como no soportada."""
    try:
        data = json.loads(raw)
        query_type = AllowedQueryType(data.get("query_type"))
    except (ValueError, TypeError, AttributeError):
        return None
    if query_type not in allowed:
        return None
    date_from, date_to = _date(data.get("date_from")), _date(data.get("date_to"))
    filters = tuple((str(f["key"]), str(f["value"])) for f in data.get("filters") or []
                    if isinstance(f, dict) and f.get("key") and f.get("value"))
    try:
        date_range = DateRange(date_from, date_to) if date_from and date_to else None
        return InsightQuery(query_type, date_range, filters)
    except BusinessRuleError:
        return None


def _date(value) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


class UnavailableTextGenerator:
    """Se usa cuando no hay GEMINI_API_KEY: siempre falla y los casos de uso devuelven el texto de reserva."""

    def generate(self, prompt: str) -> str:
        raise GeminiUnavailableError("GEMINI_API_KEY no está configurada.")


class UnavailableQueryPlanner:
    def plan(self, question: str, allowed: tuple[AllowedQueryType, ...]) -> InsightQuery | None:
        raise GeminiUnavailableError("GEMINI_API_KEY no está configurada.")
