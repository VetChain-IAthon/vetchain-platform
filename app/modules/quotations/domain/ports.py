from __future__ import annotations

from datetime import date
from typing import Protocol

from app.core.application import Page, Paging
from app.core.domain import DateRange, Money, Ruc
from app.modules.quotations.domain.entities import OrderRef, Product, Quotation
from app.modules.quotations.domain.value_objects import CustomerTerms, PricingTerms, QuotationStatus, ReferencePrice


class QuotationRepository(Protocol):
    def add(self, quotation: Quotation) -> Quotation: ...

    def get(self, quotation_id: int) -> Quotation | None: ...

    def list(
        self, status: QuotationStatus | None, ruc: Ruc | None, date_range: DateRange | None, paging: Paging,
        salesperson_code: str | None = None,
    ) -> Page[Quotation]: ...

    def list_issued(self) -> list[Quotation]: ...

    def save(self, quotation: Quotation) -> None: ...


class ProductCatalog(Protocol):
    def search(self, text: str | None, family: str | None, paging: Paging) -> Page[Product]: ...

    def get(self, code: str) -> Product | None: ...

    def reference_prices(self, codes: list[str]) -> dict[str, ReferencePrice]:
        """Último precio pagado por producto."""
        ...

    def unit_costs(self, codes: list[str]) -> dict[str, Money]:
        """Costos unitarios. Hoy los CSV no traen costos: devuelve un dict vacío."""
        ...


class OrderLookup(Protocol):
    def orders_since(self, since: date) -> list[OrderRef]: ...


class CustomerTermsGateway(Protocol):
    def terms_for(self, ruc: Ruc) -> CustomerTerms: ...

    def ensure_access(self, ruc: Ruc) -> None: ...


class SettingsGateway(Protocol):
    def pricing_terms(self) -> PricingTerms: ...
