from datetime import date, datetime
from decimal import Decimal

import pytest

from app.core.application import Page, Paging
from app.core.domain import BusinessRuleError, DataOrigin, DateRange, FixedClock, Money, Percentage, Ruc


def test_money_rounds_to_cents_and_operates():
    assert Money("10.005").amount == Decimal("10.01")
    assert Money("10") + Money("2.50") == Money("12.50")
    assert Money("10") - Money("12") == Money("-2")
    assert Money("3.33").times(3) == Money("9.99")
    assert Money("200").percent(Percentage(18)) == Money("36")
    assert Money("10").divided_by(3) == Money("3.33")
    assert Money.total([Money("1"), Money("2")]) == Money("3")


def test_money_rejects_float():
    with pytest.raises(TypeError):
        Money(0.1)


@pytest.mark.parametrize("value", ["-1", "100.01"])
def test_percentage_out_of_range(value):
    with pytest.raises(BusinessRuleError):
        Percentage(value)


def test_ruc_needs_11_digits():
    assert Ruc(" 20123456789 ").value == "20123456789"
    for bad in ("2012345678", "2012345678A"):
        with pytest.raises(BusinessRuleError):
            Ruc(bad)


def test_date_range():
    assert DateRange(date(2026, 1, 1), date(2026, 1, 31)).days == 31
    with pytest.raises(BusinessRuleError):
        DateRange(date(2026, 2, 1), date(2026, 1, 1))


def test_least_reliable_origin():
    assert DataOrigin.least_reliable([DataOrigin.REAL, DataOrigin.ESTIMATED]) is DataOrigin.ESTIMATED
    assert DataOrigin.least_reliable({DataOrigin.REAL}) is DataOrigin.REAL


def test_paging_and_page():
    paging = Paging(page=3, per_page=10)
    assert paging.offset == 20
    assert Page.of(["a"], total=21, paging=paging).items == ("a",)
    with pytest.raises(BusinessRuleError):
        Paging(page=0)
    with pytest.raises(BusinessRuleError):
        Paging(per_page=101)


def test_fixed_clock():
    clock = FixedClock(datetime(2026, 10, 13, 9, 0))
    assert clock.today() == date(2026, 10, 13)
