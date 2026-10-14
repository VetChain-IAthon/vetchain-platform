"""Casos de uso de customers con puertos falsos en memoria."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.application import Page, Paging, SessionUser
from app.core.domain import BusinessRuleError, FixedClock, ForbiddenError, Money, NotFoundError, Ruc
from app.modules.customers.application import use_cases as uc
from app.modules.customers.domain.entities import Customer, CustomerActivity
from app.modules.customers.domain.value_objects import LevelThresholds, SalespersonScope
from tests.application.fakes import FakeUnitOfWork

A, B = Ruc("20111111111"), Ruc("20222222222")
MANAGER = SessionUser(1, "manager", None)
SELLER = SessionUser(2, "salesperson", "002")


class FakeCustomers:
    def __init__(self) -> None:
        self.customers = {A: Customer(A, "ALFA", "987654321", salesperson_code="001"), B: Customer(B, "BETA", salesperson_code="002")}
        self.dates = {A: (date(2025, 1, 10), date(2025, 2, 10)), B: (date(2024, 1, 5),)}
        self.amounts = {A: Decimal(300), B: Decimal(100)}

    def get(self, ruc):
        return self.customers.get(ruc)

    def all_in_scope(self, scope, text=None):
        return [c for c in self.customers.values() if scope.includes(c.salesperson_code) and (not text or text.lower() in c.name.lower())]

    def latest_order_date(self):
        return date(2025, 2, 10)

    def last_order_dates(self, rucs):
        return {r: max(self.dates[r]) for r in rucs}

    def activity(self, rucs, since):
        result = {}
        for r in rucs:
            dates = tuple(d for d in self.dates[r] if d >= since)
            result[r] = CustomerActivity(r, Money(self.amounts[r] if dates else 0), len(dates), dates)
        return result


class FakeSettings:
    def __init__(self, thresholds=None) -> None:
        self.thresholds = thresholds

    def level_thresholds(self):
        return self.thresholds


class FakeContacts:
    def __init__(self) -> None:
        self.items = []

    def add(self, contact):
        from dataclasses import replace

        contact = replace(contact, id=len(self.items) + 1)
        self.items.append(contact)
        return contact

    def list_for(self, ruc, paging):
        found = [c for c in self.items if c.ruc == ruc]
        return Page.of(found, len(found), paging)


def test_scope_forces_salesperson_code():
    assert uc.scope_for(MANAGER).is_everyone
    assert uc.scope_for(MANAGER, "001").salesperson_code == "001"
    assert uc.scope_for(SELLER, "001").salesperson_code == "002"
    with pytest.raises(BusinessRuleError):
        uc.scope_for(SessionUser(3, "salesperson", None))


def test_list_customers_uses_window_and_levels():
    customers = FakeCustomers()
    result = uc.ListCustomers(customers, FakeSettings(), FakeUnitOfWork()).execute(uc.ListCustomersQuery(), SalespersonScope.everyone())
    rows = result.page.items
    assert [r.standing.customer.ruc for r in rows] == [A, B] and not result.levels_configured
    assert rows[1].standing.activity_12m.order_count == 0  # su pedido es de antes de la ventana
    assert rows[1].standing.last_order_date == date(2024, 1, 5) and rows[0].share_pct == Decimal("100.0")

    thresholds = LevelThresholds(Money(Decimal(100)), Money(Decimal(250)))
    result = uc.ListCustomers(customers, FakeSettings(thresholds), FakeUnitOfWork()).execute(
        uc.ListCustomersQuery(level="C", paging=Paging(1, 10)), SalespersonScope.everyone()
    )
    assert [r.standing.customer.ruc for r in result.page.items] == [B]


def test_detail_respects_scope():
    use_case = uc.GetCustomer(FakeCustomers(), FakeSettings(), FakeUnitOfWork())
    with pytest.raises(ForbiddenError):
        use_case.execute(A.value, uc.scope_for(SELLER))
    with pytest.raises(NotFoundError):
        use_case.execute("20999999999", uc.scope_for(MANAGER))
    detail = use_case.execute(A.value, uc.scope_for(MANAGER))
    assert detail.rhythm.average_days == Decimal(31) and detail.average_order_amount_12m == Money(Decimal(150))


def test_register_contact_uses_today_and_commits():
    contacts, uow = FakeContacts(), FakeUnitOfWork()
    clock = FixedClock(datetime(2026, 10, 13, 9, 0))
    contact = uc.RegisterContact(FakeCustomers(), contacts, clock, uow).execute(
        uc.RegisterContactCommand(B.value, "No contestó"), SELLER, uc.scope_for(SELLER)
    )
    assert contact.id == 1 and contact.contact_date == date(2026, 10, 13) and contact.user_id == SELLER.id
    assert uow.commits == 1
    with pytest.raises(BusinessRuleError):
        uc.RegisterContact(FakeCustomers(), contacts, clock, uow).execute(
            uc.RegisterContactCommand(B.value, "   "), SELLER, uc.scope_for(SELLER)
        )
