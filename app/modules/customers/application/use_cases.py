"""Casos de uso de customers (fase 1): cartera, ficha, pedidos, productos, condiciones, contactos y WhatsApp.

Los montos son pedidos sin IGV de productos veterinarios: un pedido no es una venta facturada.
La ventana de 12 meses termina en la fecha de corte de los datos (el último pedido cargado).
"""
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from app.core.application import Page, Paging, SessionUser
from app.core.domain import BusinessRuleError, Clock, ConflictError, Money, NotFoundError, Ruc, UnitOfWork
from app.modules.customers.domain.entities import (
    Contact,
    Customer,
    CustomerActivity,
    CustomerDiscard,
    CustomerStanding,
    OrderSummary,
    PeriodOrder,
    PeriodProduct,
    ProductPurchase,
)
from app.modules.customers.domain.ports import (
    ContactRepository,
    CustomerReadRepository,
    DiscardRepository,
    SettingsGateway,
    UserDirectoryGateway,
)
from app.modules.customers.domain.services import (
    AlertPrioritizer,
    DormancyEvaluator,
    LevelClassifier,
    ShareCalculator,
    SuggestedMessage,
    TwelveMonthWindow,
    WhatsappLinkBuilder,
)
from app.modules.customers.domain.value_objects import (
    CommercialTerms,
    ContactOutcome,
    CustomerStatus,
    DiscardReason,
    Level,
    PurchaseRhythm,
    SalespersonScope,
)


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
class DormantCustomersQuery:
    search: str | None = None
    customer_type: str | None = None  # company | person
    paging: Paging = Paging()


@dataclass(frozen=True)
class DormantCustomer:
    customer: Customer
    lifetime: CustomerActivity  # historial completo: pedidos, monto y última compra


@dataclass(frozen=True)
class DormantCustomerList:
    page: Page[DormantCustomer]
    data_as_of: date | None
    customer_count: int  # cartera visible, sin filtros
    dormant_count: int  # sin pedidos en 12 meses, sin filtros y sin los descartados
    ordered_before_count: int  # de los dormidos, los que sí tienen pedidos antes
    type_counts: dict[str, int]  # dormidos que coinciden con la búsqueda, por tipo; "all" los suma todos
    discarded_count: int = 0  # descartados vigentes de la cartera visible


def _is_dormant(activity: CustomerActivity, window_start: date | None) -> bool:
    """Sin pedidos en la ventana de 12 meses (o nunca)."""
    last = activity.last_order_date
    return last is None or window_start is None or last < window_start


def _matches(customer: Customer, text: str) -> bool:
    return (not text or text in customer.name.casefold() or text in (customer.region or "").casefold()
            or customer.ruc.value.startswith(text))


def _count_types(customers: list[Customer]) -> dict[str, int]:
    counts = {"all": len(customers)}
    for customer in customers:
        kind = customer.customer_type or "other"
        counts[kind] = counts.get(kind, 0) + 1
    return counts


class ListDormantCustomers:
    """Clientes sin pedidos en la ventana de 12 meses, ordenados por monto histórico (sin IGV, solo veterinarios).

    Incluye a los que nunca tuvieron pedidos en los archivos y deja fuera a los descartados.
    No es el estado «dormido» por ritmo de compra de las alertas, que espera los factores de gerencia:
    aquí basta con no haber pedido en 12 meses.
    """

    def __init__(self, customers: CustomerReadRepository, uow: UnitOfWork, discards: DiscardRepository) -> None:
        self.customers, self.uow, self.discards = customers, uow, discards

    def execute(self, query: DormantCustomersQuery, scope: SalespersonScope) -> DormantCustomerList:
        with self.uow:
            as_of = _data_as_of(self.customers)
            found = self.customers.all_in_scope(scope)
            discarded = self.discards.active()
            visible = [c for c in found if c.ruc not in discarded]
            lifetime = self.customers.activity([c.ruc for c in visible], date.min) if visible else {}
            window_start = TwelveMonthWindow.start(as_of) if as_of else None

            dormant = []
            for customer in visible:
                act = lifetime.get(customer.ruc, _empty_activity(customer.ruc))
                if _is_dormant(act, window_start):
                    dormant.append(DormantCustomer(customer, act))
            dormant.sort(key=lambda d: (-d.lifetime.amount.amount, d.customer.name))
            ordered_before = sum(1 for d in dormant if d.lifetime.order_count)

            text = (query.search or "").strip().casefold()
            matching = [d for d in dormant if _matches(d.customer, text)]
            type_counts = _count_types([d.customer for d in matching])
            if query.customer_type:
                matching = [d for d in matching if d.customer.customer_type == query.customer_type]

            paging = query.paging
            chunk = matching[paging.offset:paging.offset + paging.per_page]
            return DormantCustomerList(
                Page.of(chunk, len(matching), paging), as_of, len(found), len(dormant), ordered_before, type_counts,
                len(found) - len(visible),
            )


@dataclass(frozen=True)
class DiscardCustomerCommand:
    ruc: str
    reason: str
    note: str | None = None


class DiscardCustomer:
    """Descarta a un cliente dormido (cerró, cambió de datos o ya no es viable). Solo se descartan clientes sin
    pedidos en 12 meses; queda registrado quién y cuándo, y se puede restaurar."""

    def __init__(self, customers: CustomerReadRepository, discards: DiscardRepository, clock: Clock, uow: UnitOfWork) -> None:
        self.customers, self.discards, self.clock, self.uow = customers, discards, clock, uow

    def execute(self, command: DiscardCustomerCommand, user: SessionUser, scope: SalespersonScope) -> CustomerDiscard:
        try:
            reason = DiscardReason(command.reason)
        except ValueError:
            raise BusinessRuleError("Elige un motivo de descarte válido.", "invalid_discard_reason") from None
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(command.ruc), scope)
            if self.discards.active_for(customer.ruc) is not None:
                raise ConflictError("Este cliente ya está descartado.", "customer_already_discarded")
            as_of = _data_as_of(self.customers)
            act = self.customers.activity([customer.ruc], date.min).get(customer.ruc, _empty_activity(customer.ruc))
            if not _is_dormant(act, TwelveMonthWindow.start(as_of) if as_of else None):
                raise BusinessRuleError("Solo se pueden descartar clientes sin pedidos en los últimos 12 meses.",
                                        "customer_not_dormant")
            discard = self.discards.add(CustomerDiscard(customer.ruc, reason, command.note, user.id, self.clock.today()))
            self.uow.commit()
            return discard


class RestoreCustomer:
    """Devuelve un cliente descartado a la lista de dormidos. El descarte queda en el historial."""

    def __init__(self, customers: CustomerReadRepository, discards: DiscardRepository, clock: Clock, uow: UnitOfWork) -> None:
        self.customers, self.discards, self.clock, self.uow = customers, discards, clock, uow

    def execute(self, ruc: str, user: SessionUser, scope: SalespersonScope) -> None:
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(ruc), scope)
            discard = self.discards.active_for(customer.ruc)
            if discard is None:
                raise NotFoundError("Este cliente no está descartado.", "customer_not_discarded")
            self.discards.save(replace(discard, restored_by=user.id, restored_on=self.clock.today()))
            self.uow.commit()


@dataclass(frozen=True)
class DiscardedCustomersQuery:
    search: str | None = None
    reason: str | None = None
    paging: Paging = Paging()


@dataclass(frozen=True)
class DiscardedCustomer:
    customer: Customer
    lifetime: CustomerActivity
    discard: CustomerDiscard
    discarded_by_name: str | None

    @property
    def ordered_after_discard(self) -> bool:
        """Volvió a pedir después de descartarlo: conviene revisarlo y quizá restaurarlo."""
        last = self.lifetime.last_order_date
        return last is not None and last > self.discard.discarded_on


@dataclass(frozen=True)
class DiscardedCustomerList:
    page: Page[DiscardedCustomer]
    data_as_of: date | None
    discarded_count: int  # vigentes de la cartera visible, sin filtros
    reason_counts: dict[str, int]  # que coinciden con la búsqueda, por motivo; "all" los suma todos


class ListDiscardedCustomers:
    """Clientes descartados vigentes, del descarte más reciente al más antiguo."""

    def __init__(self, customers: CustomerReadRepository, discards: DiscardRepository, users: UserDirectoryGateway,
                 uow: UnitOfWork) -> None:
        self.customers, self.discards, self.users, self.uow = customers, discards, users, uow

    def execute(self, query: DiscardedCustomersQuery, scope: SalespersonScope) -> DiscardedCustomerList:
        if query.reason:
            try:
                DiscardReason(query.reason)
            except ValueError:
                raise BusinessRuleError("Elige un motivo de descarte válido.", "invalid_discard_reason") from None
        with self.uow:
            as_of = _data_as_of(self.customers)
            discards = self.discards.active()
            found = [c for c in self.customers.all_in_scope(scope) if c.ruc in discards]
            found.sort(key=lambda c: (discards[c.ruc].discarded_on, discards[c.ruc].id or 0), reverse=True)
            text = (query.search or "").strip().casefold()
            matching = [c for c in found if _matches(c, text)]
            reason_counts = {"all": len(matching)}
            for c in matching:
                key = discards[c.ruc].reason.value
                reason_counts[key] = reason_counts.get(key, 0) + 1
            if query.reason:
                matching = [c for c in matching if discards[c.ruc].reason.value == query.reason]

            paging = query.paging
            chunk = matching[paging.offset:paging.offset + paging.per_page]
            lifetime = self.customers.activity([c.ruc for c in chunk], date.min) if chunk else {}
            names = self.users.names(sorted({discards[c.ruc].discarded_by for c in chunk})) if chunk else {}
            rows = [DiscardedCustomer(c, lifetime.get(c.ruc, _empty_activity(c.ruc)), discards[c.ruc],
                                      names.get(discards[c.ruc].discarded_by)) for c in chunk]
            return DiscardedCustomerList(Page.of(rows, len(matching), paging), as_of, len(found), reason_counts)


# Factores propuestos en SIGUIENTES-PASOS.md (decisión pendiente #2 de gerencia). Cuando se decidan, irán a Ajustes.
PROVISIONAL_AT_RISK_FACTOR = Decimal("1.5")
PROVISIONAL_DORMANT_FACTOR = Decimal("3")
PROVISIONAL_DEFAULT_RHYTHM_DAYS = Decimal("30")


@dataclass(frozen=True)
class AtRiskCustomer:
    customer: Customer
    last_order_date: date
    days_since_last_order: int
    rhythm: PurchaseRhythm | None  # None: menos de dos pedidos en 12 meses, se usó el ritmo por defecto
    money_at_stake: Money  # pedido promedio de 12 meses
    amount_12m: Money = Money.zero()  # monto de pedidos de 12 meses, sin IGV
    order_count_12m: int = 0  # pedidos de 12 meses con los que se calculó el pedido promedio


@dataclass(frozen=True)
class AtRiskCustomerList:
    page: Page[AtRiskCustomer]
    data_as_of: date | None
    at_risk_factor: Decimal
    default_rhythm_days: Decimal


class ListAtRiskCustomers:
    """Clientes con pedidos en 12 meses que ya pasaron más de 1,5 veces su ritmo de compra sin pedir (sin llegar a dormidos),
    ordenados por dinero en juego. Los factores son provisionales hasta que gerencia los defina."""

    def __init__(self, customers: CustomerReadRepository, uow: UnitOfWork) -> None:
        self.customers, self.uow = customers, uow

    def execute(self, scope: SalespersonScope, paging: Paging) -> AtRiskCustomerList:
        with self.uow:
            as_of = _data_as_of(self.customers)
            at_risk = _at_risk_customers(self.customers, scope, as_of)
            chunk = at_risk[paging.offset:paging.offset + paging.per_page]
            return AtRiskCustomerList(Page.of(chunk, len(at_risk), paging), as_of, PROVISIONAL_AT_RISK_FACTOR,
                                      PROVISIONAL_DEFAULT_RHYTHM_DAYS)


def _at_risk_customers(customers: CustomerReadRepository, scope: SalespersonScope, as_of: date | None) -> list[AtRiskCustomer]:
    """Clientes en riesgo de la cartera visible, de mayor a menor dinero en juego."""
    found = customers.all_in_scope(scope)
    if as_of is None or not found:
        return []
    evaluator = DormancyEvaluator(PROVISIONAL_AT_RISK_FACTOR, PROVISIONAL_DORMANT_FACTOR, PurchaseRhythm(PROVISIONAL_DEFAULT_RHYTHM_DAYS))
    activity = customers.activity([c.ruc for c in found], TwelveMonthWindow.start(as_of))
    at_risk = []
    for customer in found:
        act = activity.get(customer.ruc)
        if act is None or act.last_order_date is None:
            continue
        rhythm = PurchaseRhythm.from_order_dates(act.order_dates)
        if evaluator.evaluate(act.last_order_date, rhythm, as_of) is CustomerStatus.AT_RISK:
            at_risk.append(AtRiskCustomer(customer, act.last_order_date, (as_of - act.last_order_date).days,
                                          rhythm, AlertPrioritizer.money_at_stake(act), act.amount, act.order_count))
    at_risk.sort(key=lambda item: (-item.money_at_stake.amount, item.customer.name))
    return at_risk


@dataclass(frozen=True)
class FollowUpBucket:
    outcome: str | None  # None = sin contactar
    customer_count: int
    money_at_stake: Money


@dataclass(frozen=True)
class SalespersonFollowUp:
    salesperson_code: str
    salesperson_name: str
    buckets: tuple[FollowUpBucket, ...]
    customer_count: int
    money_at_stake: Money


class GetAtRiskFollowUp:
    """Por vendedor: qué pasó con sus clientes en riesgo. Cuenta el último contacto desde el último pedido del cliente;
    si no hay, el cliente está «sin contactar». Las carteras son provisionales (ficha del cliente en Defontana)."""

    def __init__(self, customers: CustomerReadRepository, contacts: ContactRepository, uow: UnitOfWork) -> None:
        self.customers, self.contacts, self.uow = customers, contacts, uow

    def execute(self, scope: SalespersonScope) -> list[SalespersonFollowUp]:
        with self.uow:
            at_risk = _at_risk_customers(self.customers, scope, _data_as_of(self.customers))
            latest = self.contacts.latest_contacts([item.customer.ruc for item in at_risk])
            groups: dict[str, dict[str | None, list[AtRiskCustomer]]] = {}
            for item in at_risk:
                contact = latest.get(item.customer.ruc)
                outcome = contact.outcome.value if contact and contact.contact_date >= item.last_order_date else None
                groups.setdefault(item.customer.salesperson_code or "", {}).setdefault(outcome, []).append(item)
            names = self.customers.salesperson_names(list(groups))
            result = []
            for code, by_outcome in groups.items():
                buckets = tuple(FollowUpBucket(outcome, len(items), Money.total([i.money_at_stake for i in items]))
                                for outcome, items in by_outcome.items())
                result.append(SalespersonFollowUp(code, names.get(code, code or "Sin vendedor"), buckets,
                                                  sum(b.customer_count for b in buckets),
                                                  Money.total([b.money_at_stake for b in buckets])))
            result.sort(key=lambda f: (-f.money_at_stake.amount, f.salesperson_name))
            return result


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


BRIEF_PROJECTIONS = ("month", "semester", "year")


@dataclass(frozen=True)
class CustomerBriefQuery:
    ruc: str
    date_from: date | None = None  # por defecto, 12 meses antes de `date_to`
    date_to: date | None = None  # por defecto, la fecha de corte de los datos
    projection: str = "month"


@dataclass(frozen=True)
class BriefProduct:
    purchase: PeriodProduct
    reference_price: Money | None  # último precio pagado por cualquier cliente (estimado)

    @property
    def below_reference_pct(self) -> Decimal | None:
        """Cuánto por debajo (positivo) o por encima (negativo) de la referencia pagó en promedio."""
        paid = self.purchase.average_price
        if paid is None or self.reference_price is None or self.reference_price.amount <= 0:
            return None
        return ((self.reference_price.amount - paid.amount) * 100 / self.reference_price.amount).quantize(Decimal("0.1"))


@dataclass(frozen=True)
class MonthlyAmount:
    month: str  # AAAA-MM
    amount: Money
    order_count: int


@dataclass(frozen=True)
class CustomerBrief:
    """Ficha para reunión (versión interna). Solo cifras reales de pedidos; lo que necesita el modelo de predicción,
    Gemini, costos, lotes o cobros enlazados va como aviso en `warnings`, nunca como cifra inventada."""

    customer: Customer
    level: Level | None
    credit_days: int | None
    date_from: date
    date_to: date
    data_as_of: date | None
    projection: str
    amount: Money
    order_count: int
    average_order_amount: Money
    share_pct: Decimal  # % del monto de todos los clientes en el período
    rank: int | None  # puesto por monto en el período; None sin pedidos
    ranked_customers: int
    salesperson_name: str | None
    salesperson_share_pct: Decimal | None  # % de sus pedidos del período que atendió su vendedor asignado
    rhythm: PurchaseRhythm | None
    last_order_date: date | None  # en todo el historial hasta `date_to`
    days_since_last_order: int | None
    days_late: int | None  # días por encima de su ritmo; 0 si va al día
    invoice_discount: Money
    list_amount: Money
    monthly: tuple[MonthlyAmount, ...]
    order_dates: tuple[date, ...]
    products: tuple[BriefProduct, ...]
    warnings: tuple[str, ...]

    @property
    def expected_next_order(self) -> date | None:
        if self.last_order_date is None or self.rhythm is None:
            return None
        return self.last_order_date + timedelta(days=int(self.rhythm.average_days.to_integral_value()))


class GetCustomerBrief:
    """Ficha del cliente para reunión en un período: cuánto pidió, a qué precio, su ritmo y su vendedor.

    Proyección, ganancia, ofertas, guion, resumen y cobranza quedan pendientes (avisos) hasta que existan el modelo
    de predicción, Gemini, costos validados, lotes y cobros enlazados con pedidos.
    """

    def __init__(self, customers: CustomerReadRepository, settings: SettingsGateway, uow: UnitOfWork) -> None:
        self.customers, self.settings, self.uow = customers, settings, uow

    def execute(self, query: CustomerBriefQuery, scope: SalespersonScope) -> CustomerBrief:
        if query.projection not in BRIEF_PROJECTIONS:
            raise BusinessRuleError("La proyección debe ser month, semester o year.", "invalid_projection")
        with self.uow:
            customer = _customer_in_scope(self.customers, Ruc(query.ruc), scope)
            as_of = _data_as_of(self.customers)
            date_to = query.date_to or as_of
            if date_to is None:
                raise BusinessRuleError("Aún no hay pedidos cargados para armar la ficha.", "no_order_data")
            date_from = query.date_from or TwelveMonthWindow.start(date_to)
            if date_from > date_to:
                raise BusinessRuleError("La fecha inicial debe ser anterior o igual a la final.", "invalid_period")

            orders = self.customers.period_orders(customer.ruc, date_from, date_to)
            products = self.customers.period_products(customer.ruc, date_from, date_to)
            amounts = self.customers.amounts_by_customer(date_from, date_to)
            references = self.customers.reference_prices([p.product_code for p in products], date_to)
            history = self.customers.activity([customer.ruc], date.min)[customer.ruc]
            past_dates = [d for d in history.order_dates if d <= date_to]
            last_order = max(past_dates) if past_dates else None

            amount = Money.total([o.amount for o in orders])
            total = Money.total(list(amounts.values()))
            ranking = sorted(amounts, key=lambda ruc: (-amounts[ruc].amount, ruc))
            rank = ranking.index(customer.ruc.value) + 1 if customer.ruc.value in amounts else None
            rhythm = PurchaseRhythm.from_order_dates([o.order_date for o in orders])
            days_since = (date_to - last_order).days if last_order else None
            days_late = (max(0, days_since - int(rhythm.average_days.to_integral_value()))
                         if rhythm and days_since is not None else None)
            level, credit_days = self._level_and_credit(customer.ruc, as_of)
            assigned = customer.salesperson_code
            names = self.customers.salesperson_names([assigned]) if assigned else {}
            seller_share = (ShareCalculator.share_pct(Money.total([o.amount for o in orders if o.salesperson_code == assigned]), amount)
                            if assigned and orders else None)

            warnings = ["order_statuses_provisional", "projection_unavailable", "no_cost_data", "ai_unavailable",
                        "no_lot_data", "receipts_not_linked"]
            if level is None:
                warnings.append("thresholds_not_configured")
            return CustomerBrief(
                customer=customer, level=level, credit_days=credit_days, date_from=date_from, date_to=date_to,
                data_as_of=as_of, projection=query.projection, amount=amount, order_count=len(orders),
                average_order_amount=amount.divided_by(len(orders)) if orders else Money.zero(),
                share_pct=ShareCalculator.share_pct(amount, total), rank=rank, ranked_customers=len(amounts),
                salesperson_name=names.get(assigned) if assigned else None, salesperson_share_pct=seller_share,
                rhythm=rhythm, last_order_date=last_order, days_since_last_order=days_since, days_late=days_late,
                invoice_discount=Money.total([o.invoice_discount for o in orders]),
                list_amount=Money.total([o.list_amount for o in orders]),
                monthly=_monthly(orders, date_from, date_to),
                order_dates=tuple(o.order_date for o in orders),
                products=tuple(BriefProduct(p, references.get(p.product_code)) for p in products),
                warnings=tuple(warnings),
            )

    def _level_and_credit(self, ruc: Ruc, as_of: date | None) -> tuple[Level | None, int | None]:
        """Nivel por el monto de 12 meses (como en toda la app) y días de crédito de ese nivel, si gerencia los definió."""
        thresholds = self.settings.level_thresholds()
        if thresholds is None or as_of is None:
            return None, None
        level = LevelClassifier(thresholds).classify(self.customers.activity([ruc], TwelveMonthWindow.start(as_of))[ruc].amount)
        try:
            return level, self.settings.commercial_terms(level).credit_days
        except BusinessRuleError:
            return level, None


def _monthly(orders: list[PeriodOrder], date_from: date, date_to: date) -> tuple[MonthlyAmount, ...]:
    """Monto y pedidos por mes, con los meses sin pedidos en cero."""
    by_month: dict[str, list[PeriodOrder]] = {}
    for order in orders:
        by_month.setdefault(order.order_date.strftime("%Y-%m"), []).append(order)
    months, year, month = [], date_from.year, date_from.month
    while (year, month) <= (date_to.year, date_to.month):
        key = f"{year:04d}-{month:02d}"
        found = by_month.get(key, [])
        months.append(MonthlyAmount(key, Money.total([o.amount for o in found]), len(found)))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return tuple(months)
