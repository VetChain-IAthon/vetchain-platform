"""Pruebas de la capa de infraestructura de base de datos (SQLite) con datos mínimos."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.infrastructure.db.repositories import queries
from app.infrastructure.db.source_models import Customer, Order, OrderLine, Product, StockBalance
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.loaders.defontana_csv import find_files, load_directory, load_source, parse_rows
from tests.defontana_sample import CUSTOMERS, KARDEX, LINES, ORDERS, PRODUCTS, SALESPEOPLE, SPEC, load_sample

@pytest.fixture()
def loaded(db):
    load_sample(db)
    return db


# --- cargador -------------------------------------------------------------------------------------


def test_empty_optional_text_is_null_and_counted():
    records, report = parse_rows(SPEC["customers"], CUSTOMERS)
    maria = records[1]
    assert maria["phone"] is None and maria["email"] is None and maria["condition_code"] is None
    assert report.warnings["phone vacío"] == 2
    assert report.warnings["email vacío"] == 2


def test_derived_columns():
    customers, _ = parse_rows(SPEC["customers"], CUSTOMERS)
    assert [c["tax_id_kind"] for c in customers] == ["company", "person", "other"]
    products, _ = parse_rows(SPEC["products"], PRODUCTS)
    assert [(p["prefix"], p["is_core_product"]) for p in products] == [("MED", True), ("MED", True), ("REV", False)]
    orders, _ = parse_rows(SPEC["orders"], ORDERS)
    assert [o["is_dispatched"] for o in orders] == [True, False, False, False]
    assert orders[3]["status_code"] is None
    lines, report = parse_rows(SPEC["order_lines"], LINES)
    assert [line["is_bonus"] for line in lines][:3] == [False, False, True]
    assert [line["dup_seq"] for line in lines if line["order_no"] == "P2"] == [0, 1]
    assert report.warnings["línea repetida (pedido, línea)"] == 1
    kardex, _ = parse_rows(SPEC["stock_balances"], KARDEX)
    assert kardex[0]["period_end"] == date(2025, 1, 31)


def test_codes_keep_leading_zeros():
    records, _ = parse_rows(SPEC["salespeople"], SALESPEOPLE)
    assert records[0]["code"] == "001"


def test_required_empty_or_invalid_rejects_row():
    bad = [
        ["P9", "", "20111111111", "X", "001", "X", "001", "1", "0", "0", "1", "T"],
        ["P8", "2025-01-01", "20111111111", "X", "001", "X", "001", "uno", "0", "0", "1", "T"],
        ["P7", "2025-01-01"],
    ]
    records, report = parse_rows(SPEC["orders"], bad)
    assert records == []
    assert report.rejected == {"falta order_date": 1, "subtotal inválido": 1, "se esperaban 12 columnas": 1}
    assert report.rejected_samples[0] == (1, "falta order_date")


def test_missing_foreign_key_rejects_row():
    records, report = parse_rows(SPEC["orders"], ORDERS[:1], {"customers": set(), "salespeople": {"001"}})
    assert records == [] and report.rejected == {"ruc no existe en customers": 1}


def test_upsert_is_idempotent_and_updates(loaded):
    count = loaded.scalar(select(func.count()).select_from(OrderLine))
    load_sample(loaded)
    assert loaded.scalar(select(func.count()).select_from(OrderLine)) == count
    changed = [row.copy() for row in CUSTOMERS]
    changed[0][1] = "VET UNO RENOMBRADA S.A.C."
    load_source(loaded, SPEC["customers"], changed)
    loaded.commit()
    assert loaded.get(Customer, "20111111111").name == "VET UNO RENOMBRADA S.A.C."
    assert loaded.scalar(select(func.count()).select_from(Customer)) == 3


def test_stock_balances_accept_codes_outside_catalog(loaded):
    assert loaded.get(StockBalance, ("001", 2025, 2, "SRV0000001")) is not None
    assert queries.products_missing_from_catalog(loaded) == ["SRV0000001"]


def test_find_files_accepts_both_naming_styles(tmp_path: Path):
    names = ["1_clientes", "mederi-2-pedidos", "3_detalle", "4_productos", "5_kardex", "6_cobros", "7_vendedores"]
    for name in names:
        (tmp_path / f"{name}.csv").write_text("")
    assert sorted(find_files(tmp_path)) == [1, 2, 3, 4, 5, 6, 7]
    (tmp_path / "6_cobros.csv").unlink()
    with pytest.raises(FileNotFoundError):
        find_files(tmp_path)


# --- consultas -------------------------------------------------------------------------------------


def test_last_order_per_customer_excludes_cancelled_and_non_core(loaded):
    rows = {row["ruc"]: row for row in queries.last_order_per_customer(loaded)}
    uno = rows["20111111111"]
    assert uno["last_order_date"] == date(2025, 2, 15)  # P3 está cancelado
    assert uno["order_count"] == 2
    assert uno["amount"] == Decimal("145.01")  # 80 + 20 + 0.01 + 45; la revista no cuenta
    with_cancelled = {r["ruc"]: r for r in queries.last_order_per_customer(loaded, exclude_statuses=())}
    assert with_cancelled["20111111111"]["last_order_date"] == date(2025, 2, 20)
    assert queries.last_order_per_customer(loaded, as_of=date(2025, 1, 31))[0]["order_count"] == 1


def test_customer_orders_paginates(loaded):
    page, total = queries.customer_orders(loaded, "20111111111", per_page=2)
    assert total == 3
    assert [order["order_no"] for order in page] == ["P3", "P2"]
    page, total = queries.customer_orders(loaded, "20111111111", date_from=date(2025, 2, 1), date_to=date(2025, 2, 16))
    assert total == 1 and page[0]["order_no"] == "P2"


def test_customer_products_excludes_bonus_from_amount(loaded):
    rows = {row["product_code"]: row for row in queries.customer_products(loaded, "20111111111")}
    assert set(rows) == {"MED0000001", "MED0000002"}
    antibiotic = rows["MED0000001"]
    assert antibiotic["amount"] == Decimal("125.00")  # 80 + 45; la bonificada no suma
    assert antibiotic["quantity"] == Decimal("4")  # 2 + 1 bonificada + 1
    assert antibiotic["order_count"] == 2


def test_last_paid_price_is_estimated_and_skips_bonus_and_cancelled(loaded):
    price = queries.last_paid_price(loaded, "MED0000001")
    assert price["unit_price"] == Decimal("45.00")  # P2: 50 con 10 % de descuento; P3 está cancelado
    assert price["data_origin"] == "estimated"
    assert queries.last_paid_price(loaded, "NO-EXISTE") is None


def test_monthly_sales(loaded):
    rows = queries.monthly_sales(loaded)
    assert [(r["month"], r["order_count"], r["amount"], r["dispatched_amount"]) for r in rows] == [
        ("2025-01", 1, Decimal("100.01"), Decimal("100.01")),
        ("2025-02", 1, Decimal("45.00"), Decimal("0.00")),
        ("2025-03", 1, Decimal("10.00"), Decimal("0.00")),
    ]


def test_stock_at_uses_last_balance_up_to_month(loaded):
    feb = {row["product_code"]: row for row in queries.stock_at(loaded, 2025, 2)}
    assert feb["MED0000001"]["balance"] == Decimal("15")  # enero de ambos almacenes
    mar = {row["product_code"]: row for row in queries.stock_at(loaded, 2025, 3)}
    assert mar["MED0000001"]["balance"] == Decimal("12")  # 7 (marzo, 001) + 5 (enero, 002)
    assert queries.stock_at(loaded, 2024, 12) == []


def test_receipts_by_customer(loaded):
    rows = queries.receipts_by_customer(loaded, "20111111111")
    assert [row["receipt_no"] for row in rows] == ["R2", "R1"]
    assert queries.receipts_by_customer(loaded, "20111111111", date_from=date(2025, 2, 1))[0]["amount"] == Decimal("59.00")


# --- unidad de trabajo -----------------------------------------------------------------------------


def test_unit_of_work_rolls_back_without_commit(db):
    load_sample(db)
    with SqlAlchemyUnitOfWork() as uow:
        uow.session.get(Product, "MED0000001").name = "CAMBIADO"
    with SqlAlchemyUnitOfWork() as uow:
        assert uow.session.get(Product, "MED0000001").name == "ANTIBIOTICO X 20"
        uow.session.get(Product, "MED0000001").name = "CAMBIADO"
        uow.commit()
    with SessionLocal() as session:
        assert session.get(Product, "MED0000001").name == "CAMBIADO"


# --- datos reales (solo si los CSV están en la máquina) ---------------------------------------------

REAL_DATA = next((path for path in (Path("data/defontana"), Path("data")) if len(list(path.glob("*.csv"))) >= 7), None)


@pytest.mark.skipif(REAL_DATA is None, reason="Los CSV reales no están en data/defontana ni en data/")
def test_real_csv_load_has_expected_counts(db):
    reports = {report.table: report for report in load_directory(db, REAL_DATA)}
    assert {table: report.rows_loaded for table, report in reports.items()} == {
        "salespeople": 6, "customers": 1330, "products": 115, "orders": 14945,
        "order_lines": 67403, "stock_balances": 9970, "receipts": 14082,
    }
    assert all(report.rows_rejected == 0 for report in reports.values())
    assert reports["order_lines"].warnings["línea repetida (pedido, línea)"] == 18
    assert db.scalar(select(func.count()).select_from(Order)) == 14945
