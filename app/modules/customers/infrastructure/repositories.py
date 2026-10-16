"""Lectura de clientes, pedidos y productos desde las tablas de Defontana (solo lectura)."""
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.application import Page, Paging
from app.core.domain import Money, Ruc
from app.infrastructure.db.repositories import queries
from app.infrastructure.db.source_models import Customer as CustomerRow
from app.infrastructure.db.source_models import Order as OrderRow
from app.infrastructure.db.source_models import Salesperson as SalespersonRow
from app.modules.customers.domain.entities import (
    Contact,
    Customer,
    CustomerActivity,
    CustomerDiscard,
    OrderSummary,
    PeriodOrder,
    PeriodProduct,
    ProductPurchase,
)
from app.modules.customers.domain.value_objects import ContactOutcome, DiscardReason, SalespersonScope
from app.modules.customers.infrastructure.orm import ContactRow, CustomerDiscardRow


def _to_customer(row: CustomerRow) -> Customer:
    return Customer(
        ruc=Ruc(row.ruc),
        name=row.name,
        phone=row.phone,
        email=row.email,
        region=row.department,
        customer_type=row.tax_id_kind,
        salesperson_code=row.salesperson_code,
    )


class SqlAlchemyCustomerReadRepository:
    """Implementa CustomerReadRepository. Los montos son sin IGV y solo de productos veterinarios;
    los pedidos excluidos son los de `exclude_statuses` (por defecto, cancelados)."""

    def __init__(self, session: Session, exclude_statuses: tuple[str, ...] = queries.DEFAULT_EXCLUDED) -> None:
        self._session = session
        self._exclude = exclude_statuses

    def get(self, ruc: Ruc) -> Customer | None:
        row = self._session.get(CustomerRow, ruc.value)
        return None if row is None else _to_customer(row)

    def search(self, text: str | None, scope: SalespersonScope, paging: Paging) -> Page[Customer]:
        filters = self._scope_filters(scope) + self._text_filters(text)
        total = self._session.scalar(select(func.count()).select_from(CustomerRow).where(*filters))
        rows = self._session.scalars(
            select(CustomerRow).where(*filters).order_by(CustomerRow.name, CustomerRow.ruc)
            .offset(paging.offset).limit(paging.per_page)
        )
        return Page.of([_to_customer(row) for row in rows], total, paging)

    def all_in_scope(self, scope: SalespersonScope, text: str | None = None) -> list[Customer]:
        filters = self._scope_filters(scope) + self._text_filters(text)
        rows = self._session.scalars(select(CustomerRow).where(*filters).order_by(CustomerRow.ruc))
        return [_to_customer(row) for row in rows]

    def latest_order_date(self) -> date | None:
        return self._session.scalar(select(func.max(OrderRow.order_date)))

    def last_order_dates(self, rucs: list[Ruc]) -> dict[Ruc, date]:
        wanted = {ruc.value: ruc for ruc in rucs}
        rows = queries.last_order_per_customer(self._session, exclude_statuses=self._exclude)
        return {wanted[row["ruc"]]: row["last_order_date"] for row in rows if row["ruc"] in wanted}

    def activity(self, rucs: list[Ruc], since: date) -> dict[Ruc, CustomerActivity]:
        found = queries.customer_activity(self._session, [ruc.value for ruc in rucs], since, self._exclude)
        result = {}
        for ruc in rucs:
            item = found.get(ruc.value, {"amount": 0, "order_count": 0, "order_dates": []})
            result[ruc] = CustomerActivity(ruc, Money(item["amount"]), item["order_count"], tuple(item["order_dates"]))
        return result

    def orders(self, ruc: Ruc, paging: Paging) -> Page[OrderSummary]:
        rows, total = queries.customer_orders(self._session, ruc.value, page=paging.page, per_page=paging.per_page)
        items = [
            OrderSummary(
                order_no=row["order_no"],
                order_date=row["order_date"],
                amount=Money(row["subtotal"] - row["discount"]),
                total_with_tax=Money(row["total"]),
                status_code=row["status_code"],
                salesperson_code=row["salesperson_code"],
            )
            for row in rows
        ]
        return Page.of(items, total, paging)

    def products(self, ruc: Ruc) -> list[ProductPurchase]:
        return [
            ProductPurchase(
                product_code=row["product_code"],
                product_name=row["product_name"],
                category_code=row["category_code"],
                times_ordered=row["order_count"],
                total_quantity=row["quantity"],
                amount=Money(row["amount"]),
                last_order_date=row["last_order_date"],
            )
            for row in queries.customer_products(self._session, ruc.value, self._exclude)
        ]

    def period_orders(self, ruc: Ruc, date_from: date, date_to: date) -> list[PeriodOrder]:
        return [
            PeriodOrder(row["order_no"], row["order_date"], row["salesperson_code"], Money(row["amount"]), Money(row["list_amount"]))
            for row in queries.customer_period_orders(self._session, ruc.value, date_from, date_to, self._exclude)
        ]

    def period_products(self, ruc: Ruc, date_from: date, date_to: date) -> list[PeriodProduct]:
        return [
            PeriodProduct(row["product_code"], row["product_name"], row["category_code"], row["order_count"],
                          row["quantity"], Money(row["amount"]), row["last_order_date"])
            for row in queries.customer_period_products(self._session, ruc.value, date_from, date_to, self._exclude)
        ]

    def amounts_by_customer(self, date_from: date, date_to: date) -> dict[str, Money]:
        rows = queries.amounts_by_customer(self._session, date_from, date_to, self._exclude)
        return {row["ruc"]: Money(row["amount"]) for row in rows}

    def reference_prices(self, product_codes: list[str], as_of: date) -> dict[str, Money]:
        return {code: Money(price) for code, price in queries.last_paid_prices(self._session, product_codes, as_of).items()}

    def salesperson_names(self, codes: list[str]) -> dict[str, str]:
        if not codes:
            return {}
        rows = self._session.execute(select(SalespersonRow.code, SalespersonRow.name).where(SalespersonRow.code.in_(codes)))
        return {code: " ".join(name.split()).title() for code, name in rows}

    @staticmethod
    def _text_filters(text: str | None) -> list:
        text = (text or "").strip()
        return [or_(CustomerRow.name.ilike(f"%{text}%"), CustomerRow.ruc.like(f"{text}%"))] if text else []

    @staticmethod
    def _scope_filters(scope: SalespersonScope) -> list:
        return [] if scope.is_everyone else [CustomerRow.salesperson_code == scope.salesperson_code]


class SqlAlchemyContactRepository:
    """Implementa ContactRepository sobre la tabla contacts (propia de la app)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, contact: Contact) -> Contact:
        row = ContactRow(ruc=contact.ruc.value, user_id=contact.user_id, outcome=contact.outcome.value, contact_date=contact.contact_date)
        self._session.add(row)
        self._session.flush()
        return _to_contact(row)

    def get(self, contact_id: int) -> Contact | None:
        row = self._session.get(ContactRow, contact_id)
        return _to_contact(row) if row else None

    def remove(self, contact_id: int) -> None:
        row = self._session.get(ContactRow, contact_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def list_for(self, ruc: Ruc, paging: Paging) -> Page[Contact]:
        filters = [ContactRow.ruc == ruc.value]
        total = self._session.scalar(select(func.count()).select_from(ContactRow).where(*filters))
        rows = self._session.scalars(
            select(ContactRow).where(*filters).order_by(ContactRow.contact_date.desc(), ContactRow.id.desc())
            .offset(paging.offset).limit(paging.per_page)
        )
        return Page.of([_to_contact(row) for row in rows], total, paging)

    def latest_contacts(self, rucs: list[Ruc]) -> dict[Ruc, Contact]:
        if not rucs:
            return {}
        rows = self._session.scalars(
            select(ContactRow).where(ContactRow.ruc.in_([ruc.value for ruc in rucs]))
            .order_by(ContactRow.ruc, ContactRow.contact_date.desc(), ContactRow.id.desc())
        )
        latest: dict[Ruc, Contact] = {}
        for row in rows:
            latest.setdefault(Ruc(row.ruc), _to_contact(row))
        return latest


def _to_contact(row: ContactRow) -> Contact:
    return Contact(Ruc(row.ruc), row.user_id, ContactOutcome(row.outcome), row.contact_date, id=row.id)


class SqlAlchemyDiscardRepository:
    """Implementa DiscardRepository sobre la tabla customer_discards (propia de la app)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def active_for(self, ruc: Ruc) -> CustomerDiscard | None:
        row = self._session.scalar(
            select(CustomerDiscardRow).where(CustomerDiscardRow.ruc == ruc.value, CustomerDiscardRow.restored_on.is_(None))
            .order_by(CustomerDiscardRow.id.desc()).limit(1)
        )
        return None if row is None else _to_discard(row)

    def active(self) -> dict[Ruc, CustomerDiscard]:
        rows = self._session.scalars(
            select(CustomerDiscardRow).where(CustomerDiscardRow.restored_on.is_(None)).order_by(CustomerDiscardRow.id)
        )
        return {Ruc(row.ruc): _to_discard(row) for row in rows}

    def add(self, discard: CustomerDiscard) -> CustomerDiscard:
        row = CustomerDiscardRow(ruc=discard.ruc.value, reason=discard.reason.value, note=discard.note,
                                 discarded_by=discard.discarded_by, discarded_on=discard.discarded_on)
        self._session.add(row)
        self._session.flush()
        return _to_discard(row)

    def save(self, discard: CustomerDiscard) -> None:
        row = self._session.get(CustomerDiscardRow, discard.id)
        row.restored_by, row.restored_on = discard.restored_by, discard.restored_on
        self._session.flush()


def _to_discard(row: CustomerDiscardRow) -> CustomerDiscard:
    return CustomerDiscard(Ruc(row.ruc), DiscardReason(row.reason), row.note, row.discarded_by, row.discarded_on,
                           row.restored_by, row.restored_on, id=row.id)
