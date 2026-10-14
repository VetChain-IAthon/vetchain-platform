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


def test_valid_order_row():
    validator = CsvRowValidator(SOURCES[SourceName.ORDERS].schema)
    record, error = validator.validate(1, ["P001", "13/10/2026", "20123456789", "", "100.50", "", "", "118.59", "A"])
    assert error is None
    assert record["order_date"] == date(2026, 10, 13)
    assert record["subtotal"] == Decimal("100.50")
    assert record["salesperson_code"] is None


def test_invalid_rows_report_line_and_reason():
    validator = CsvRowValidator(SOURCES[SourceName.STOCK_BALANCES].schema)
    _, error = validator.validate(7, ["01", "2026"])
    assert error.line == 7 and "5 columnas" in error.message
    _, error = validator.validate(8, ["01", "dos mil", "10", "P1", "abc"])
    assert "'year'" in error.message and "'balance'" in error.message


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
