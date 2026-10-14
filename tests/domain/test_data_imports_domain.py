from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, ConflictError, DataOrigin
from app.modules.data_imports.domain.entities import DataImport, ImportStatus
from app.modules.data_imports.domain.services import CsvRowValidator
from app.modules.data_imports.domain.sources import SOURCES, SourceName

NOW = datetime(2026, 10, 13, 10, 0)


def test_there_are_seven_sources():
    assert set(SOURCES) == set(SourceName)


ORDER = ["00203913", "2026-10-13", "20123456789", "VET SAC", "001", "OFICINA", "001", "100.50", "0.00", "18.09", "118.59", ""]


def test_valid_order_row_uses_csv_positions():
    validator = CsvRowValidator(SOURCES[SourceName.ORDERS].schema)
    record, error = validator.validate(1, ORDER)
    assert error is None
    assert record["order_no"] == "00203913"
    assert record["order_date"] == date(2026, 10, 13)
    assert record["salesperson_code"] == "001"
    assert record["subtotal"] == Decimal("100.50")
    assert record["status_code"] is None
    assert "VET SAC" not in record.values()  # c3 repite el nombre del cliente: no se guarda


def test_invalid_rows_report_line_and_reason():
    validator = CsvRowValidator(SOURCES[SourceName.STOCK_BALANCES].schema)
    _, error = validator.validate(7, ["001", "2026"])
    assert error.line == 7 and "6 columnas" in error.message
    _, error = validator.validate(8, ["001", "dos mil", "10", "MED1", "", "abc"])
    assert error.message == "year inválido; balance inválido."
    _, error = validator.validate(9, ["001", "2026", "10", "", "", "1"])
    assert error.message == "falta product_code."


def _import(**overrides):
    data = dict(source=SourceName.ORDERS, origin=DataOrigin.REAL, rows_read=10, rows_with_error=2, created_at=NOW)
    data.update(overrides)
    return DataImport(**data)


def test_import_state_machine():
    confirmed = _import().confirm(NOW)
    assert confirmed.status is ImportStatus.CONFIRMED and confirmed.decided_at == NOW
    with pytest.raises(ConflictError):
        confirmed.cancel(NOW)
    assert _import().cancel(NOW).status is ImportStatus.CANCELLED


def test_import_rules():
    with pytest.raises(BusinessRuleError):
        _import(origin=DataOrigin.ESTIMATED)
    with pytest.raises(BusinessRuleError):
        _import(rows_with_error=11)
    with pytest.raises(BusinessRuleError):
        _import(rows_with_error=10).confirm(NOW)
