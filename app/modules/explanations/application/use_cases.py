"""Casos de uso de explanations. Gemini solo ve cifras agregadas; si falla o no hay clave, hay texto de reserva."""
import json
import logging

from app.core.domain import BusinessRuleError
from app.modules.explanations.domain.entities import (
    AggregatedFigures,
    AllowedQueryType,
    Explanation,
    ExplanationSource,
    InsightAnswer,
)
from app.modules.explanations.domain.ports import (
    CustomerNameSource,
    FallbackTextBuilder,
    InsightQueryRunner,
    PromptRepository,
    QueryPlanner,
    TextGenerator,
)
from app.modules.explanations.domain.services import PrivacyGuard

logger = logging.getLogger(__name__)

ALERT_PROMPT = "alert_explanation"
ANSWER_PROMPT = "insight_answer"
MAX_QUESTION_LENGTH = 500


class ExplainAlert:
    """Explica en pocas frases por qué conviene contactar a un cliente, solo con `AggregatedFigures`."""

    def __init__(self, prompts: PromptRepository, generator: TextGenerator, fallback: FallbackTextBuilder) -> None:
        self.prompts, self.generator, self.fallback = prompts, generator, fallback

    def execute(self, figures: AggregatedFigures) -> Explanation:
        try:
            prompt = self.prompts.get(ALERT_PROMPT).format(**figures.as_prompt_values())
            return Explanation(self.generator.generate(prompt), ExplanationSource.AI)
        except Exception:  # cualquier fallo de la IA cae al texto de reserva; nunca rompe la alerta
            logger.warning("Explicación de alerta con texto de reserva", exc_info=True)
            return Explanation(self.fallback.build(figures), ExplanationSource.FALLBACK)


class AskInsightQuestion:
    """Pregunta en lenguaje natural → consulta permitida → cifras de la base → resumen.

    La IA no responde con datos propios: solo elige la consulta y redacta sobre las filas agregadas que devuelve la base.
    """

    def __init__(self, planner: QueryPlanner, runner: InsightQueryRunner, generator: TextGenerator,
                 prompts: PromptRepository, customer_names: CustomerNameSource) -> None:
        self.planner, self.runner, self.generator = planner, runner, generator
        self.prompts, self.customer_names = prompts, customer_names

    def execute(self, question: str) -> InsightAnswer:
        question = question.strip()
        if not question:
            raise BusinessRuleError("Escribe una pregunta.", "empty_question")
        if len(question) > MAX_QUESTION_LENGTH:
            raise BusinessRuleError(f"La pregunta no puede pasar de {MAX_QUESTION_LENGTH} caracteres.", "question_too_long")
        guard = PrivacyGuard(self.customer_names.names())
        guard.check_text(question)  # antes de enviarla a la IA

        try:
            query = self.planner.plan(question, tuple(AllowedQueryType))
        except BusinessRuleError:
            raise
        except Exception as error:
            logger.warning("No se pudo interpretar la pregunta con la IA", exc_info=True)
            raise BusinessRuleError("La IA no está disponible ahora. Intenta más tarde o usa los reportes.",
                                    "ai_unavailable") from error
        if query is None:
            raise BusinessRuleError("No puedo responder esa pregunta con los datos disponibles. Prueba con pedidos por "
                                    "mes, por familia, productos principales o desempeño de vendedores.",
                                    "question_not_supported")
        guard.check_query(query)

        result = self.runner.run(query)
        if not result.rows:
            return InsightAnswer("No hay pedidos en el período consultado.", result.sources, result.data_origin)
        try:
            prompt = self.prompts.get(ANSWER_PROMPT).format(
                question=question, rows=json.dumps(list(result.rows), ensure_ascii=False, indent=1))
            text = self.generator.generate(prompt)
        except Exception:
            logger.warning("Respuesta a la pregunta con texto de reserva", exc_info=True)
            text = _plain_rows(result.rows)
        return InsightAnswer(text, result.sources, result.data_origin)


def _plain_rows(rows: tuple[dict[str, str], ...]) -> str:
    lines = ["; ".join(f"{key}: {value}" for key, value in row.items()) for row in rows]
    return "Resultado de la consulta:\n" + "\n".join(f"- {line}" for line in lines)
