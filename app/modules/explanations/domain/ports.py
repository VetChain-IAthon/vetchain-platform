from typing import Protocol

from app.modules.explanations.domain.entities import (
    AggregatedFigures,
    AggregatedResult,
    AllowedQueryType,
    InsightQuery,
)


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> str:
        """Lanza una excepción si el servicio de IA falla; el caso de uso usa el texto de reserva."""
        ...


class QueryPlanner(Protocol):
    def plan(self, question: str, allowed: tuple[AllowedQueryType, ...]) -> InsightQuery | None:
        """Convierte la pregunta en una consulta permitida, o None si no se puede."""
        ...


class InsightQueryRunner(Protocol):
    def run(self, query: InsightQuery) -> AggregatedResult: ...


class FallbackTextBuilder(Protocol):
    def build(self, figures: AggregatedFigures) -> str: ...


class PromptRepository(Protocol):
    def get(self, name: str) -> str: ...
