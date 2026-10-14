from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from app.core.domain import BusinessRuleError, ConflictError, Money, Percentage, Ruc
from app.core.domain.numbers import to_decimal
from app.modules.quotations.domain.value_objects import ApprovalStatus, Margin, QuotationStatus, ReferencePrice


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    family: str | None = None


@dataclass(frozen=True)
class QuotationLine:
    product_code: str
    quantity: Decimal
    unit_price: ReferencePrice
    unit_cost: Money | None = None

    def __post_init__(self) -> None:
        quantity = to_decimal(self.quantity)
        if quantity <= 0:
            raise BusinessRuleError("La cantidad debe ser mayor que cero.", "invalid_quantity")
        if self.unit_price.price.is_negative:
            raise BusinessRuleError("El precio no puede ser negativo.", "invalid_price")
        object.__setattr__(self, "quantity", quantity)

    @property
    def amount(self) -> Money:
        return self.unit_price.price.times(self.quantity)

    @property
    def cost(self) -> Money | None:
        return None if self.unit_cost is None else self.unit_cost.times(self.quantity)


@dataclass(frozen=True)
class QuotationTotals:
    """`net` es sin IGV; `total_with_tax` incluye IGV."""

    subtotal: Money
    discount_amount: Money
    net: Money
    igv: Money
    total_with_tax: Money
    margin: Margin


@dataclass(frozen=True)
class OrderRef:
    """Pedido mínimo para enlazar conversiones."""

    order_no: str
    ruc: Ruc
    order_date: date


@dataclass(frozen=True)
class Quotation:
    """Raíz del agregado. Una cotización emitida no se edita: solo pasa a converted o expired."""

    ruc: Ruc
    user_id: int
    lines: tuple[QuotationLine, ...]
    discount: Percentage
    totals: QuotationTotals
    approval: ApprovalStatus
    issued_on: date
    valid_until: date
    status: QuotationStatus = QuotationStatus.ISSUED
    order_no: str | None = None
    id: int | None = None

    @classmethod
    def issue(
        cls,
        ruc: Ruc,
        user_id: int,
        lines: "list[QuotationLine] | tuple[QuotationLine, ...]",
        discount: Percentage,
        totals: QuotationTotals,
        approval: ApprovalStatus,
        issued_on: date,
        validity_days: int,
    ) -> "Quotation":
        if not lines:
            raise BusinessRuleError("La cotización debe tener al menos una línea.", "empty_quotation")
        codes = [line.product_code for line in lines]
        if len(codes) != len(set(codes)):
            raise BusinessRuleError("Un producto no puede repetirse en la cotización.", "duplicated_product")
        if approval.blocks_issue:
            raise BusinessRuleError(
                "La cotización necesita aprobación de gerencia antes de emitirse.", "approval_required"
            )
        return cls(
            ruc=ruc,
            user_id=user_id,
            lines=tuple(lines),
            discount=discount,
            totals=totals,
            approval=approval,
            issued_on=issued_on,
            valid_until=issued_on + timedelta(days=validity_days),
        )

    def convert(self, order_no: str) -> "Quotation":
        self._ensure_issued()
        return replace(self, status=QuotationStatus.CONVERTED, order_no=order_no)

    def expire(self, today: date) -> "Quotation":
        self._ensure_issued()
        if today <= self.valid_until:
            raise ConflictError("La cotización todavía está vigente.", "quotation_still_valid")
        return replace(self, status=QuotationStatus.EXPIRED)

    def _ensure_issued(self) -> None:
        if self.status is not QuotationStatus.ISSUED:
            raise ConflictError("La cotización ya no está vigente.", "quotation_closed")
