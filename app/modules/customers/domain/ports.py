from __future__ import annotations  # AlertRepository.list oculta al tipo list dentro de la clase

from datetime import date
from typing import Protocol

from app.core.application import Page, Paging
from app.core.domain import Money, Ruc
from app.modules.customers.domain.entities import (
    Alert,
    AlertExplanation,
    AlertFigures,
    Contact,
    Customer,
    CustomerActivity,
    CustomerDiscard,
    OrderSummary,
    PeriodOrder,
    PeriodProduct,
    ProductPurchase,
)
from app.modules.customers.domain.value_objects import CommercialTerms, Level, LevelThresholds, Probability, SalespersonScope


class CustomerReadRepository(Protocol):
    """Lectura de las tablas de los CSV (customers, orders, order_lines). Nunca escribe."""

    def get(self, ruc: Ruc) -> Customer | None: ...

    def search(self, text: str | None, scope: SalespersonScope, paging: Paging) -> Page[Customer]: ...

    def all_in_scope(self, scope: SalespersonScope, text: str | None = None) -> list[Customer]:
        """Toda la cartera visible, filtrada por nombre o RUC si llega `text`."""
        ...

    def latest_order_date(self) -> date | None:
        """Fecha de corte de los datos: el pedido más reciente cargado."""
        ...

    def last_order_dates(self, rucs: list[Ruc]) -> dict[Ruc, date]:
        """Último pedido de cada cliente en todo el historial."""
        ...

    def activity(self, rucs: list[Ruc], since: date) -> dict[Ruc, CustomerActivity]: ...

    def orders(self, ruc: Ruc, paging: Paging) -> Page[OrderSummary]: ...

    def products(self, ruc: Ruc) -> list[ProductPurchase]: ...

    def period_orders(self, ruc: Ruc, date_from: date, date_to: date) -> list[PeriodOrder]:
        """Pedidos del cliente en el período, del más antiguo al más reciente."""
        ...

    def period_products(self, ruc: Ruc, date_from: date, date_to: date) -> list[PeriodProduct]: ...

    def amounts_by_customer(self, date_from: date, date_to: date) -> dict[str, Money]:
        """Monto pedido de cada cliente con pedidos en el período (por RUC). Base del ranking y la participación."""
        ...

    def reference_prices(self, product_codes: list[str], as_of: date) -> dict[str, Money]:
        """Último precio pagado por unidad de cada producto hasta `as_of`, a cualquier cliente (estimado)."""
        ...

    def salesperson_names(self, codes: list[str]) -> dict[str, str]:
        """Nombre de cada vendedor por código."""
        ...


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

    def get(self, contact_id: int) -> Contact | None: ...

    def remove(self, contact_id: int) -> None: ...

    def latest_contacts(self, rucs: list[Ruc]) -> dict[Ruc, Contact]:
        """El contacto más reciente de cada cliente que tenga alguno."""
        ...


class PredictionGateway(Protocol):
    def predict_many(self, rucs: list[Ruc]) -> dict[Ruc, Probability]: ...


class ExplanationGateway(Protocol):
    def explain(self, figures: AlertFigures) -> AlertExplanation: ...


class SettingsGateway(Protocol):
    def level_thresholds(self) -> LevelThresholds | None:
        """None mientras gerencia no defina los umbrales."""
        ...

    def commercial_terms(self, level: Level) -> CommercialTerms:
        """BusinessRuleError si faltan las reglas del nivel."""
        ...


class DiscardRepository(Protocol):
    def active_for(self, ruc: Ruc) -> CustomerDiscard | None: ...

    def active(self) -> dict[Ruc, CustomerDiscard]:
        """Descartes vigentes (sin restaurar), por cliente."""
        ...

    def add(self, discard: CustomerDiscard) -> CustomerDiscard: ...

    def save(self, discard: CustomerDiscard) -> None:
        """Guarda la restauración de un descarte existente."""
        ...


class UserDirectoryGateway(Protocol):
    def names(self, user_ids: list[int]) -> dict[int, str]:
        """Nombre completo de cada usuario que exista."""
        ...
