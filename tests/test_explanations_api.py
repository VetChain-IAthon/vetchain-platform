"""Interfaz de explanations: POST /insights/questions con Gemini falso, y sin clave."""
import os
from datetime import date
from decimal import Decimal

import pytest

from app.main import app
from app.modules.explanations.application import public
from app.modules.explanations.domain.entities import AllowedQueryType, InsightQuery
from app.modules.explanations.infrastructure.gemini import parse_plan
from app.modules.explanations.interface import dependencies as deps
from tests.defontana_sample import load_sample

URL = "/api/v1/insights/questions"


class _Planner:
    def __init__(self, query):
        self.query = query

    def plan(self, question, allowed):
        return self.query


class _Generator:
    def generate(self, prompt):
        raise RuntimeError("sin red")  # fuerza el texto de reserva para comparar las filas reales


@pytest.fixture()
def manager(login, db):
    headers = login("manager")
    load_sample(db)
    return headers


@pytest.fixture()
def fake_ai(monkeypatch):
    def _use(query):
        monkeypatch.setattr(deps, "query_planner", lambda: _Planner(query))
        monkeypatch.setattr(deps, "text_generator", lambda: _Generator())
    return _use


def test_answers_from_reports_with_sources(client, manager, fake_ai):
    fake_ai(InsightQuery(AllowedQueryType.TOP_PRODUCTS))
    response = client.post(URL, headers=manager, json={"question": "¿Qué productos se piden más?"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["data_origin"] == "real" and data["sources"][0].startswith("/reports/sales?from=")
    assert "MED0000001" in data["text"] and "125.00" in data["text"]


def test_unavailable_queries_and_unsupported_filters(client, manager, fake_ai):
    fake_ai(InsightQuery(AllowedQueryType.RECEIVABLES_AGING))
    response = client.post(URL, headers=manager, json={"question": "¿Cuánta deuda vencida hay?"})
    assert response.status_code == 400 and response.json()["error"]["code"] == "query_not_available"
    fake_ai(InsightQuery(AllowedQueryType.SALES_BY_MONTH, filters=(("region", "Lima"),)))
    response = client.post(URL, headers=manager, json={"question": "¿Cuánto se pidió en Lima?"})
    assert response.json()["error"]["code"] == "filter_not_supported"


def test_without_api_key_questions_report_ai_unavailable(client, manager, monkeypatch):
    monkeypatch.setattr(deps.settings, "gemini_api_key", "")
    response = client.post(URL, headers=manager, json={"question": "¿Cuánto se pidió por mes?"})
    assert response.status_code == 400 and response.json()["error"]["code"] == "ai_unavailable"


def test_without_api_key_alert_explanation_uses_fallback(monkeypatch):
    monkeypatch.setattr(deps.settings, "gemini_api_key", "")
    result = public.explain_alert(public.AlertFiguresInput(40, None, Decimal("0.5"), Decimal(300), ()))
    assert result.source == "fallback" and result.text.startswith("Lleva 40 días sin comprar.")


def test_questions_are_manager_only(client, login):
    response = client.post(URL, headers=login("salesperson"), json={"question": "¿Cuánto se pidió?"})
    assert response.status_code == 403


def test_parse_plan_only_accepts_the_closed_list():
    allowed = tuple(AllowedQueryType)
    query = parse_plan('{"query_type": "sales_by_month", "date_from": "2025-01-01", "date_to": "2025-03-31",'
                       ' "filters": [{"key": "salesperson_code", "value": "002"}]}', allowed)
    assert query.date_range.from_date == date(2025, 1, 1) and query.filters == (("salesperson_code", "002"),)
    assert parse_plan('{"query_type": "unsupported"}', allowed) is None
    assert parse_plan('{"query_type": "drop_table"}', allowed) is None
    assert parse_plan("no es json", allowed) is None
    assert parse_plan('{"query_type": "top_products", "filters": [{"key": "ruc", "value": "1"}]}', allowed) is None
    assert parse_plan('{"query_type": "top_products", "date_from": "2025-05-01", "date_to": "2025-01-01"}', allowed) is None


@pytest.mark.skipif(not os.getenv("GEMINI_LIVE_TEST"), reason="Llama a Gemini de verdad: GEMINI_LIVE_TEST=1 y GEMINI_API_KEY")
def test_live_gemini_explanation():
    from app.core.config import Settings

    key = Settings().gemini_api_key
    assert key, "Falta GEMINI_API_KEY en .env"
    from unittest.mock import patch
    with patch.object(deps.settings, "gemini_api_key", key):
        result = public.explain_alert(public.AlertFiguresInput(45, Decimal(30), Decimal("0.73"), Decimal(1250), ("Antiparasitarios",)))
    print("\n", result)
    assert result.source == "ai"
