"""Repositorios de los módulos (customers y reports) sobre SQLite con datos mínimos."""
from datetime import date
from decimal import Decimal

import pytest

from app.core.application import Paging
from app.core.domain import DateRange, Money, Ruc
from app.infrastructure.loaders.defontana_csv import SPECS
from app.modules.customers.domain.value_objects import SalespersonScope
from app.modules.customers.infrastructure.repositories import SqlAlchemyCustomerReadRepository
from app.modules.data_imports.domain.sources import SOURCES, ColumnType
from app.modules.reports.domain.entities import SalesDefinition
from app.modules.reports.infrastructure.repositories import (
    SqlCustomersReadRepository,
    SqlSalesReadRepository,
    SqlStockReadRepository,
)
from tests.defontana_sample import load_sample

UNO, MARIA, DNI = Ruc("20111111111"), Ruc("10222222222"), Ruc("12345678")
YEAR_2025 = DateRange(date(2025, 1, 1), date(2025, 12, 31))


@pytest.fixture()
def session(db):
    load_sample(db)
    return db


# --- customers ------------------------------------------------------------------------------------


def test_get_maps_empty_fields_and_dni(session):
    repo = SqlAlchemyCustomerReadRepository(session)
    maria = repo.get(MARIA)
    assert maria.phone is None and maria.email is None  # vacíos en el CSV → NULL → None
    assert maria.salesperson_code == "002"
    dni = repo.get(DNI)
    assert dni.customer_type == "other" and dni.region is None
    assert repo.get(Ruc("20999999999")) is None


def test_search_respects_salesperson_scope(session):
    repo = SqlAlchemyCustomerReadRepository(session)
    assert repo.search(None, SalespersonScope.everyone(), Paging()).total == 3
    mine = repo.search(None, SalespersonScope.of_salesperson("002"), Paging())
    assert {customer.ruc for customer in mine.items} == {MARIA, DNI}
    assert [c.ruc for c in repo.search("vet", SalespersonScope.everyone(), Paging()).items] == [UNO]
    assert [c.ruc for c in repo.search("1022", SalespersonScope.everyone(), Paging()).items] == [MARIA]
    assert len(repo.all_in_scope(SalespersonScope.of_salesperson("001"))) == 1


def test_activity_excludes_cancelled_and_non_core(session):
    activity = SqlAlchemyCustomerReadRepository(session).activity([UNO, MARIA, DNI], since=date(2025, 1, 1))
    assert activity[UNO].amount == Money("145.01")
    assert activity[UNO].order_dates == (date(2025, 1, 10), date(2025, 2, 15))
    assert activity[MARIA].order_count == 1  # pedido sin estado: cuenta
    assert activity[DNI].order_count == 0 and activity[DNI].last_order_date is None
    later = SqlAlchemyCustomerReadRepository(session).activity([UNO], since=date(2025, 2, 1))
    assert later[UNO].order_count == 1


def test_orders_page_amount_is_without_tax(session):
    page = SqlAlchemyCustomerReadRepository(session).orders(UNO, Paging(per_page=2))
    assert page.total == 3 and [order.order_no for order in page.items] == ["P3", "P2"]
    assert page.items[1].amount == Money("50.00") and page.items[1].total_with_tax == Money("59.00")


def test_products_exclude_bonus_from_amount(session):
    products = {p.product_code: p for p in SqlAlchemyCustomerReadRepository(session).products(UNO)}
    assert products["MED0000001"].amount == Money("125.00")
    assert products["MED0000001"].total_quantity == Decimal("4")
    assert products["MED0000001"].category_code == "001"


# --- reports --------------------------------------------------------------------------------------


def test_monthly_amounts_follow_sales_definition(session):
    repo = SqlSalesReadRepository(session)
    months = repo.monthly_amounts(YEAR_2025, SalesDefinition())
    assert [(m.month, m.amount) for m in months] == [
        (date(2025, 1, 1), Money("100.00")),
        (date(2025, 2, 1), Money("45.00")),
        (date(2025, 3, 1), Money("10.00")),
    ]
    assert months[0].dispatched_amount == Money("100.00")
    everything = repo.monthly_amounts(YEAR_2025, SalesDefinition(frozenset()))
    assert everything[1].amount == Money("115.00")  # incluye el pedido cancelado


def test_amounts_by_category_and_customer(session):
    assert SqlSalesReadRepository(session).amounts_by_category(YEAR_2025, SalesDefinition()) == [("001", Money("155.00"))]
    assert SqlCustomersReadRepository(session).amounts_by_customer(YEAR_2025, SalesDefinition()) == [
        ("20111111111", Money("145.00")),
        ("10222222222", Money("10.00")),
    ]


def test_stock_levels(session):
    levels = {level.product_code: level for level in SqlStockReadRepository(session).levels_at(2025, 3)}
    assert levels["MED0000001"].balance == Decimal("12")
    assert "SRV0000001" not in levels  # solo productos veterinarios


# --- coherencia entre el dominio de data_imports y el cargador ------------------------------------


def test_domain_sources_match_loader_specs():
    kinds = {"text": ColumnType.TEXT, "int": ColumnType.INTEGER, "decimal": ColumnType.DECIMAL,
             "date": ColumnType.DATE, "bool": ColumnType.BOOLEAN}
    for spec in SPECS:
        source = SOURCES[spec.table]
        assert source.number == spec.number and source.schema.width == spec.width, spec.table
        assert [(c.index, c.name, c.type, c.required) for c in source.schema.columns] == [
            (f.index, f.name, kinds[f.kind], f.required) for f in spec.fields
        ], spec.table
