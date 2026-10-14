from datetime import date
from decimal import Decimal

import pytest

from app.core.domain import BusinessRuleError, ConflictError, DataOrigin, Money, Percentage, Ruc
from app.modules.quotations.domain.entities import OrderRef, Quotation, QuotationLine
from app.modules.quotations.domain.services import ApprovalPolicy, ConversionMatcher, QuotationPricer
from app.modules.quotations.domain.value_objects import Margin, QuotationStatus, ReferencePrice

RUC = Ruc("20123456789")


def _line(code="P1", qty="2", price="100", cost=None):
    return QuotationLine(code, Decimal(qty), ReferencePrice(Money(price), DataOrigin.REAL), cost and Money(cost))


def _issue(lines=None, approval=None, issued_on=date(2026, 10, 1)):
    lines = lines or [_line()]
    totals = QuotationPricer(Percentage(18)).price(lines, Percentage(10))
    approval = approval or ApprovalPolicy(Percentage(15), Percentage(10)).evaluate(Percentage(10), totals.margin)
    return Quotation.issue(RUC, 1, lines, Percentage(10), totals, approval, issued_on, validity_days=15)


def test_pricer_without_costs_has_no_margin():
    totals = QuotationPricer(Percentage(18)).price([_line(), _line("P2", "1", "50")], Percentage(10))
    assert totals.subtotal == Money("250")
    assert totals.discount_amount == Money("25")
    assert totals.net == Money("225")
    assert totals.igv == Money("40.50")
    assert totals.total_with_tax == Money("265.50")
    assert totals.margin == Margin(None, "no_cost_data")


def test_pricer_with_costs_computes_margin():
    totals = QuotationPricer(Percentage(18)).price([_line(cost="60")], Percentage(0))
    assert totals.margin.pct == Decimal("40.00")


def test_line_needs_positive_quantity():
    with pytest.raises(BusinessRuleError):
        _line(qty="0")


def test_approval_policy():
    policy = ApprovalPolicy(max_discount=Percentage(10), min_margin=Percentage(20))
    assert not policy.evaluate(Percentage(10), Margin.unknown()).required
    approval = policy.evaluate(Percentage(12), Margin(Decimal("15")))
    assert approval.reasons == ("discount_above_level_max", "margin_below_min")


def test_issue_rules():
    with pytest.raises(BusinessRuleError):
        Quotation.issue(RUC, 1, [], Percentage(0), None, None, date(2026, 10, 1), 15)
    with pytest.raises(BusinessRuleError):
        _issue(lines=[_line(), _line()])
    required = ApprovalPolicy(Percentage(5), Percentage(0)).evaluate(Percentage(10), Margin.unknown())
    with pytest.raises(BusinessRuleError):
        _issue(approval=required)
    quotation = _issue(approval=required.confirm("Cliente estratégico"))
    assert quotation.status is QuotationStatus.ISSUED
    assert quotation.valid_until == date(2026, 10, 16)


def test_conversion_and_expiration():
    quotation = _issue()
    orders = [
        OrderRef("O3", RUC, date(2026, 10, 20)),  # fuera de vigencia
        OrderRef("O2", Ruc("20999999999"), date(2026, 10, 2)),  # otro cliente
        OrderRef("O1", RUC, date(2026, 10, 5)),
    ]
    match = ConversionMatcher.match(quotation, orders)
    assert match.order_no == "O1"
    converted = quotation.convert(match.order_no)
    assert converted.status is QuotationStatus.CONVERTED
    with pytest.raises(ConflictError):
        converted.expire(date(2026, 12, 1))
    with pytest.raises(ConflictError):
        quotation.expire(date(2026, 10, 16))
    assert quotation.expire(date(2026, 10, 17)).status is QuotationStatus.EXPIRED
