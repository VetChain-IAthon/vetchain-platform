from datetime import date

from app.core.domain import Money, Percentage
from app.modules.quotations.domain.entities import OrderRef, Quotation, QuotationLine, QuotationTotals
from app.modules.quotations.domain.value_objects import ApprovalStatus, Margin


class QuotationPricer:
    """Calcula subtotal, descuento, neto sin IGV, IGV, total con IGV y margen."""

    def __init__(self, igv_rate: Percentage) -> None:
        self._igv_rate = igv_rate

    def price(self, lines: "list[QuotationLine] | tuple[QuotationLine, ...]", discount: Percentage) -> QuotationTotals:
        subtotal = Money.total([line.amount for line in lines])
        discount_amount = subtotal.percent(discount)
        net = subtotal - discount_amount
        igv = net.percent(self._igv_rate)
        costs = [line.cost for line in lines]
        if lines and all(cost is not None for cost in costs):
            margin = Margin.from_amounts(net, Money.total(costs))
        else:
            margin = Margin.unknown()
        return QuotationTotals(subtotal, discount_amount, net, igv, net + igv, margin)


class ApprovalPolicy:
    """Pide aprobación si el descuento supera el máximo del nivel o si el margen baja del mínimo."""

    def __init__(self, max_discount: Percentage, min_margin: Percentage) -> None:
        self._max_discount = max_discount
        self._min_margin = min_margin

    def evaluate(self, discount: Percentage, margin: Margin) -> ApprovalStatus:
        reasons = []
        if discount > self._max_discount:
            reasons.append("discount_above_level_max")
        if margin.is_below(self._min_margin):
            reasons.append("margin_below_min")
        return ApprovalStatus(required=bool(reasons), reasons=tuple(reasons))


class ConversionMatcher:
    """Una cotización se convierte con el primer pedido del mismo cliente entre la emisión y la vigencia."""

    @staticmethod
    def match(quotation: Quotation, orders: "list[OrderRef]") -> OrderRef | None:
        candidates = [
            order
            for order in orders
            if order.ruc == quotation.ruc and quotation.issued_on <= order.order_date <= quotation.valid_until
        ]
        return min(candidates, key=lambda order: (order.order_date, order.order_id), default=None)

    @staticmethod
    def is_expired(quotation: Quotation, today: date) -> bool:
        return today > quotation.valid_until
