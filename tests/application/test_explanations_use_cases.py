"""Casos de uso de explanations con IA falsa: sin red ni clave de Gemini."""
from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, DataOrigin, Money
from app.modules.explanations.application import use_cases as uc
from app.modules.explanations.domain.entities import (
    AggregatedFigures,
    AggregatedResult,
    AllowedQueryType,
    ExplanationSource,
    InsightQuery,
)
from app.modules.explanations.infrastructure.adapters import FilePromptRepository, TemplateFallbackTextBuilder

FIGURES = AggregatedFigures(45, Decimal("30"), Decimal("0.73"), Money("1250.5"), ("Antiparasitarios",))


class FakeGenerator:
    def __init__(self, text: str = "Texto de la IA.", fail: bool = False) -> None:
        self.text, self.fail, self.prompts = text, fail, []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("sin red")
        return self.text


class FakePlanner:
    def __init__(self, query: InsightQuery | None = None, fail: bool = False) -> None:
        self.query, self.fail, self.questions = query, fail, []

    def plan(self, question, allowed):
        self.questions.append(question)
        if self.fail:
            raise RuntimeError("sin clave")
        return self.query


class FakeRunner:
    def __init__(self, rows=({"mes": "2025-01", "monto_pedido": "100.00"},)) -> None:
        self.rows, self.queries = rows, []

    def run(self, query):
        self.queries.append(query)
        return AggregatedResult(tuple(self.rows), ("/reports/sales",), DataOrigin.REAL)


class FakeNames:
    def names(self):
        return frozenset({"Veterinaria San Martín SAC"})


def _ask(planner, runner=None, generator=None):
    return uc.AskInsightQuestion(planner, runner or FakeRunner(), generator or FakeGenerator(),
                                 FilePromptRepository(), FakeNames())


def test_explain_alert_sends_only_aggregated_figures():
    generator = FakeGenerator()
    explanation = uc.ExplainAlert(FilePromptRepository(), generator, TemplateFallbackTextBuilder()).execute(FIGURES)
    assert explanation.source is ExplanationSource.AI and explanation.text == "Texto de la IA."
    assert "45" in generator.prompts[0] and "73 %" in generator.prompts[0] and "{" not in generator.prompts[0]


def test_explain_alert_falls_back_when_ai_fails():
    explanation = uc.ExplainAlert(FilePromptRepository(), FakeGenerator(fail=True), TemplateFallbackTextBuilder()).execute(FIGURES)
    assert explanation.source is ExplanationSource.FALLBACK
    assert explanation.text.startswith("Lleva 45 días sin comprar y suele comprar cada 30 días")
    assert "73 %" in explanation.text and "Antiparasitarios" in explanation.text


def test_question_answer_comes_from_database_rows():
    planner, runner, generator = FakePlanner(InsightQuery(AllowedQueryType.SALES_BY_MONTH)), FakeRunner(), FakeGenerator("En enero se pidió S/ 100.")
    answer = _ask(planner, runner, generator).execute("¿Cuánto se pidió por mes?")
    assert answer.text == "En enero se pidió S/ 100." and answer.sources == ("/reports/sales",)
    assert answer.data_origin is DataOrigin.REAL and runner.queries[0].query_type is AllowedQueryType.SALES_BY_MONTH
    assert '"monto_pedido": "100.00"' in generator.prompts[0]


def test_question_naming_a_customer_never_reaches_the_ai():
    planner = FakePlanner(InsightQuery(AllowedQueryType.SALES_BY_MONTH))
    with pytest.raises(BusinessRuleError) as error:
        _ask(planner).execute("¿Cuánto pidió Veterinaria San Martín SAC en marzo?")
    assert error.value.code == "identifies_customer" and planner.questions == []


def test_question_errors():
    with pytest.raises(BusinessRuleError, match="Escribe"):
        _ask(FakePlanner()).execute("  ")
    with pytest.raises(BusinessRuleError) as unsupported:
        _ask(FakePlanner(None)).execute("¿Qué tiempo hará mañana?")
    assert unsupported.value.code == "question_not_supported"
    with pytest.raises(BusinessRuleError) as unavailable:
        _ask(FakePlanner(fail=True)).execute("¿Cuánto se pidió por mes?")
    assert unavailable.value.code == "ai_unavailable"


def test_answer_falls_back_to_plain_rows_and_handles_empty_period():
    planner = FakePlanner(InsightQuery(AllowedQueryType.SALES_BY_MONTH))
    answer = _ask(planner, generator=FakeGenerator(fail=True)).execute("¿Cuánto se pidió por mes?")
    assert answer.text == "Resultado de la consulta:\n- mes: 2025-01; monto_pedido: 100.00"
    empty = _ask(planner, runner=FakeRunner(rows=())).execute("¿Cuánto se pidió por mes?")
    assert empty.text == "No hay pedidos en el período consultado."
