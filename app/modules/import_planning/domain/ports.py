from decimal import Decimal
from typing import Protocol

from app.core.application import Page, Paging
from app.modules.import_planning.domain.entities import ImportSuggestion


class ImportSuggestionRepository(Protocol):
    def get(self, suggestion_id: int) -> ImportSuggestion | None: ...

    def list(self, supplier: str | None, paging: Paging) -> Page[ImportSuggestion]: ...

    def save(self, suggestion: ImportSuggestion) -> None: ...

    def replace_pending(self, suggestions: list[ImportSuggestion]) -> None:
        """Recalcula las pendientes sin tocar las que ya tienen decisión."""
        ...


class DemandGateway(Protocol):
    def monthly_demand(self, product_codes: list[str]) -> dict[str, Decimal]: ...


class StockReader(Protocol):
    def current_stock(self, product_codes: list[str]) -> dict[str, Decimal]:
        """Stock actual por producto. Falta en el dict si no hay dato validado."""
        ...
