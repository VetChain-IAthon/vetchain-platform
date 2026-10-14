from datetime import date
from typing import Protocol

from app.core.application import Page, Paging
from app.core.domain import Ruc
from app.modules.customers.domain.entities import (
    Alert,
    AlertExplanation,
    AlertFigures,
    Contact,
    Customer,
    CustomerActivity,
    OrderSummary,
    ProductPurchase,
)
from app.modules.customers.domain.value_objects import CommercialTerms, Level, LevelThresholds, Probability, SalespersonScope


class CustomerReadRepository(Protocol):
    """Lectura de las tablas de los CSV (customers, orders, order_lines). Nunca escribe."""

    def get(self, ruc: Ruc) -> Customer | None: ...

    def search(self, text: str | None, scope: SalespersonScope, paging: Paging) -> Page[Customer]: ...

    def all_in_scope(self, scope: SalespersonScope) -> list[Customer]: ...

    def activity(self, rucs: list[Ruc], since: date) -> dict[Ruc, CustomerActivity]: ...

    def orders(self, ruc: Ruc, paging: Paging) -> Page[OrderSummary]: ...

    def products(self, ruc: Ruc) -> list[ProductPurchase]: ...


class AlertRepository(Protocol):
    def get(self, alert_id: int) -> Alert | None: ...

    def list(self, alert_date: date, scope: SalespersonScope, contacted: bool | None, paging: Paging) -> Page[Alert]: ...

    def rucs_with_alert_on(self, alert_date: date) -> set[Ruc]:
        """Para respetar la regla de una alerta por cliente y día."""
        ...

    def add_many(self, alerts: list[Alert]) -> None: ...


class ContactRepository(Protocol):
    def add(self, contact: Contact) -> Contact: ...

    def list_for(self, ruc: Ruc, paging: Paging) -> Page[Contact]: ...

    def contacted_alert_ids(self, alert_ids: list[int]) -> set[int]: ...


class PredictionGateway(Protocol):
    def predict_many(self, rucs: list[Ruc]) -> dict[Ruc, Probability]: ...


class ExplanationGateway(Protocol):
    def explain(self, figures: AlertFigures) -> AlertExplanation: ...


class SettingsGateway(Protocol):
    def level_thresholds(self) -> LevelThresholds: ...

    def commercial_terms(self, level: Level) -> CommercialTerms: ...
