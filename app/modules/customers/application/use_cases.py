"""Casos de uso de customers (fase 1): cartera, ficha, pedidos, productos, condiciones, contactos y WhatsApp.

Los montos son pedidos sin IGV de productos veterinarios: un pedido no es una venta facturada.
La ventana de 12 meses termina en la fecha de corte de los datos (el último pedido cargado).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.application import Page, Paging, SessionUser
from app.core.domain import BusinessRuleError, Clock, Money, NotFoundError, Ruc, UnitOfWork
from app.modules.customers.domain.entities import (
    Contact,
    Customer,
    CustomerActivity,
    CustomerStanding,
    OrderSummary,
    ProductPurchase,
)
from app.modules.customers.domain.ports import ContactRepository, CustomerReadRepository, SettingsGateway
from app.modules.customers.domain.services import (
    LevelClassifier,
    ShareCalculator,
    SuggestedMessage,
    TwelveMonthWindow,
    WhatsappLinkBuilder,
)
from app.modules.customers.domain.value_objects import CommercialTerms, ContactOutcome, Level, PurchaseRhythm, SalespersonScope


def scope_for(user: SessionUser, requested_salesperson_code: str | None = None) -> SalespersonScope:
    """Gerencia ve todo o el vendedor que pida; un vendedor siempre ve solo su cartera."""
    if user.is_manager:
        code = (requested_salesperson_code or "").strip()
        return SalespersonScope.of_salesperson(code) if code else SalespersonScope.everyone()
    return SalespersonScope.of_salesperson(user.salesperson_code or "")


def _customer_in_scope(customers: CustomerReadRepository, ruc: Ruc, scope: SalespersonScope) -> Customer:
    customer = customers.get(ruc)
    if customer is None:
        raise NotFoundError("No existe un cliente con ese RUC.", "customer_not_found")
    scope.ensure_includes(customer.salesperson_code)
    return customer


def _data_as_of(customers: CustomerReadRepository) -> date | None:
    return customers.latest_order_date()


def _empty_activity(ruc: Ruc) -> CustomerActivity:
    return CustomerActivity(ruc, Money.zero(), 0)


@dataclass(frozen=True)
class ListCustomersQuery:
    search: str | None = None
    level: str | None = None
    paging: Paging = Paging()


@dataclass(frozen=True)
class CustomerListItem:
    standing: CustomerStanding
    share_pct: Decimal  # % del monto de 12 meses de toda la cartera visible


@dataclass(frozen=True)
class CustomerList:
    page: Page[CustomerListItem]
    data_as_of: date | None
    total_amount_12m: Money
    levels_configured: bool


class ListCustomers:
    """Cartera visible ordenada por monto de 12 meses (de mayor a menor), con nivel y participación."""

    def __init__(self, customers: CustomerReadRepository, settings: SettingsGateway, uow: UnitOfWork) -> None:
        self.customers, self.settings, self.uow = customers, settings, uow

    def execute(self, query: ListCustomersQuery, scope: SalespersonScope) -> CustomerList:
        with self.uow:
            thresholds = self.settings.level_thresholds()
            if query.level and thresholds is None:
                raise BusinessRuleError(
                    "No se puede filtrar por nivel: gerencia aún no definió los umbrales en Ajustes.", "thresholds_not_configured"
                )
            as_of = _data_as_of(self.customers)
            found = self.customers.all_in_scope(scope, query.search)
            rucs = [customer.ruc for customer in found]
            activity = self.customers.activity(rucs, TwelveMonthWindow.start(as_of)) if as_of and rucs else {}
            last_orders = self.customers.last_order_dates(rucs) if rucs else {}
            classifier = LevelClassifier(thresholds) if thresholds else None

            standings = []
            for customer in found:
                act = activity.get(customer.ruc, _empty_activity(customer.ruc))
                level = classifier.classify(act.amount) if classifier else None
                standings.append(CustomerStanding(customer, act, last_orders.get(customer.ruc), level))
            if query.level:
                standings = [s for s in standings if s.level == Level(query.level)]
            standings.sort(key=lambda s: (-s.activity_12m.amount.amount, s.customer.name))

            total = Money.total([s.activity_12m.amount for s in standings])
            paging = query.paging
            chunk = standings[paging.offset:paging.offset + paging.per_page]
            rows = [CustomerListItem(s, ShareCalculator.share_pct(s.activity_12m.amount, total)) for s in chunk]
            return CustomerList(Page.of(rows, len(standings), paging), as_of, total, thresholds is not None)


@dataclass(frozen=True)
class CustomerDetail:
    standing: CustomerStanding
    lifetime: CustomerActivity
    rhythm: PurchaseRhythm | None
    data_as_of: date | None
    levels_configured: bool

    @property
    def average_order_amount_12m(self) -> Money:
        act = self.standing.activity_12m
        return act.amount.divided_by(act.order_count) if act.order_count else Money.zero()

    @property
    def first_order_date(self) -> date | None:
        return min(self.lifetime.order_dates) if self.lifetime.order_dates else None


class GetCustomer:
    """Ficha: datos del cliente, nivel, resumen de 12 meses e historial completo."""

    def __init__(self, customers: CustomerReadRepository, settings: SettingsGateway, uow: UnitOfWork) -> None:
        self.customers, self.settings, self.uow = customers, settings, uow

    def execute(self, ruc: str, scope: SalespersonScope) -> CustomerDetail:
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(ruc), scope)
            as_of = _data_as_of(self.customers)
            act_12m = (
                self.customers.activity([customer.ruc], TwelveMonthWindow.start(as_of))[customer.ruc]
                if as_of else _empty_activity(customer.ruc)
            )
            lifetime = self.customers.activity([customer.ruc], date.min)[customer.ruc]
            thresholds = self.settings.level_thresholds()
            level = LevelClassifier(thresholds).classify(act_12m.amount) if thresholds else None
            standing = CustomerStanding(customer, act_12m, lifetime.last_order_date, level)
            return CustomerDetail(
                standing, lifetime, PurchaseRhythm.from_order_dates(lifetime.order_dates), as_of, thresholds is not None
            )


class ListCustomerOrders:
    """Historial de pedidos del cliente, del más reciente al más antiguo (todos los estados)."""

    def __init__(self, customers: CustomerReadRepository, uow: UnitOfWork) -> None:
        self.customers, self.uow = customers, uow

    def execute(self, ruc: str, scope: SalespersonScope, paging: Paging) -> Page[OrderSummary]:
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(ruc), scope)
            return self.customers.orders(customer.ruc, paging)


class ListCustomerProducts:
    """Qué productos veterinarios compra y con qué frecuencia, de mayor a menor monto."""

    def __init__(self, customers: CustomerReadRepository, uow: UnitOfWork) -> None:
        self.customers, self.uow = customers, uow

    def execute(self, ruc: str, scope: SalespersonScope) -> list[ProductPurchase]:
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(ruc), scope)
            return self.customers.products(customer.ruc)


@dataclass(frozen=True)
class CustomerTerms:
    terms: CommercialTerms
    amount_12m: Money
    data_as_of: date | None


class GetCommercialTerms:
    """Nivel del cliente y las reglas de ese nivel (margen, descuento máximo y crédito) definidas en Ajustes."""

    def __init__(self, customers: CustomerReadRepository, settings: SettingsGateway, uow: UnitOfWork) -> None:
        self.customers, self.settings, self.uow = customers, settings, uow

    def execute(self, ruc: str, scope: SalespersonScope) -> CustomerTerms:
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(ruc), scope)
            thresholds = self.settings.level_thresholds()
            if thresholds is None:
                raise BusinessRuleError(
                    "No se puede calcular el nivel: gerencia aún no definió los umbrales en Ajustes.", "thresholds_not_configured"
                )
            as_of = _data_as_of(self.customers)
            amount = (
                self.customers.activity([customer.ruc], TwelveMonthWindow.start(as_of))[customer.ruc].amount
                if as_of else Money.zero()
            )
            level = LevelClassifier(thresholds).classify(amount)
            return CustomerTerms(self.settings.commercial_terms(level), amount, as_of)


class ListContacts:
    def __init__(self, customers: CustomerReadRepository, contacts: ContactRepository, uow: UnitOfWork) -> None:
        self.customers, self.contacts, self.uow = customers, contacts, uow

    def execute(self, ruc: str, scope: SalespersonScope, paging: Paging) -> Page[Contact]:
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(ruc), scope)
            return self.contacts.list_for(customer.ruc, paging)


@dataclass(frozen=True)
class RegisterContactCommand:
    ruc: str
    outcome: str


class RegisterContact:
    """Registra que el usuario contactó al cliente hoy y qué respondió. El resultado es obligatorio."""

    def __init__(self, customers: CustomerReadRepository, contacts: ContactRepository, clock: Clock, uow: UnitOfWork) -> None:
        self.customers, self.contacts, self.clock, self.uow = customers, contacts, clock, uow

    def execute(self, command: RegisterContactCommand, user: SessionUser, scope: SalespersonScope) -> Contact:
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(command.ruc), scope)
            contact = Contact(customer.ruc, user.id, ContactOutcome(command.outcome), self.clock.today())
            contact = self.contacts.add(contact)
            self.uow.commit()
            return contact


@dataclass(frozen=True)
class WhatsappLink:
    url: str
    message: str


class BuildWhatsappLink:
    """Enlace wa.me al celular del cliente con un mensaje sugerido (o el que escriba el usuario)."""

    def __init__(self, customers: CustomerReadRepository, uow: UnitOfWork) -> None:
        self.customers, self.uow = customers, uow

    def execute(self, ruc: str, scope: SalespersonScope, message: str | None = None) -> WhatsappLink:
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(ruc), scope)
            text = (message or "").strip() or SuggestedMessage.for_customer(customer.name)
            return WhatsappLink(WhatsappLinkBuilder.build(customer.phone, text), text)
