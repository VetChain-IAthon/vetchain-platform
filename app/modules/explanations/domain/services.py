import re

from app.core.domain import BusinessRuleError
from app.modules.explanations.domain.entities import InsightQuery

_RUC_OR_DNI = re.compile(r"\b\d{8}(\d{3})?\b")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE = re.compile(r"\b9\d{8}\b")


class PrivacyGuard:
    """Rechaza cualquier texto o filtro que identifique a un cliente.

    Detecta RUC/DNI, correos, celulares y los nombres de clientes conocidos que se le pasen.
    """

    def __init__(self, customer_names: "set[str] | frozenset[str]" = frozenset()) -> None:
        self._names = {name.strip().lower() for name in customer_names if len(name.strip()) >= 4}

    def check_text(self, text: str) -> None:
        lowered = text.lower()
        if _RUC_OR_DNI.search(text) or _EMAIL.search(text) or _PHONE.search(text):
            raise self._error()
        if any(name in lowered for name in self._names):
            raise self._error()

    def check_query(self, query: InsightQuery) -> None:
        for _, value in query.filters:
            self.check_text(value)

    @staticmethod
    def _error() -> BusinessRuleError:
        return BusinessRuleError(
            "Por privacidad no se puede preguntar por un cliente específico. Pregunta por cifras agregadas.",
            "identifies_customer",
        )
