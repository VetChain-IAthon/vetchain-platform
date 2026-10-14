from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.core.schemas import JsonNumber
from app.modules.quotations.application import use_cases as uc
from app.modules.quotations.domain.entities import Quotation


class ProductOut(BaseModel):
    code: str
    name: str
    family: str | None
    reference_price: JsonNumber | None
    reference_price_origin: Literal["estimated"] | None

    @classmethod
    def from_result(cls, result: uc.ProductInfo):
        return cls(code=result.product.code, name=result.product.name, family=result.product.family,
                   reference_price=result.reference_price.price.amount if result.reference_price else None,
                   reference_price_origin="estimated" if result.reference_price else None)


class ProductPageOut(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    per_page: int


class QuotationLineIn(BaseModel):
    product_code: str = Field(min_length=1, max_length=20)
    quantity: Decimal = Field(gt=0)


class QuotationPreviewIn(BaseModel):
    ruc: str = Field(min_length=8, max_length=15)
    lines: list[QuotationLineIn] = Field(min_length=1)
    discount_pct: Decimal = Field(ge=0, le=100)

    def to_command(self) -> uc.QuotationInput:
        return uc.QuotationInput(self.ruc, tuple(uc.LineInput(x.product_code, x.quantity) for x in self.lines), self.discount_pct)


class QuotationIssueIn(QuotationPreviewIn):
    approval_confirmed: bool = False
    approval_note: str | None = Field(default=None, max_length=1000)


class QuotationLineOut(BaseModel):
    product_code: str
    quantity: JsonNumber
    unit_price: JsonNumber
    amount: JsonNumber
    data_origin: Literal["estimated"] = "estimated"

    @classmethod
    def from_domain(cls, line):
        return cls(product_code=line.product_code, quantity=line.quantity,
                   unit_price=line.unit_price.price.amount, amount=line.amount.amount)


class QuotationPreviewOut(BaseModel):
    ruc: str
    level: str
    credit_days: int
    max_discount_pct: JsonNumber
    lines: list[QuotationLineOut]
    discount_pct: JsonNumber
    subtotal: JsonNumber
    discount_amount: JsonNumber
    net: JsonNumber
    igv_rate_pct: JsonNumber
    igv: JsonNumber
    total_with_tax: JsonNumber
    margin_pct: JsonNumber | None
    warnings: list[str]
    approval_required: bool
    approval_reasons: list[str]
    quotation_validity_days: int
    data_origin: Literal["estimated"] = "estimated"

    @classmethod
    def from_result(cls, result: uc.QuotationPreview):
        t = result.totals
        return cls(ruc=result.ruc, level=result.level, credit_days=result.credit_days,
                   max_discount_pct=result.max_discount.value,
                   lines=[QuotationLineOut.from_domain(x) for x in result.lines],
                   discount_pct=result.discount.value, subtotal=t.subtotal.amount, discount_amount=t.discount_amount.amount,
                   net=t.net.amount, igv_rate_pct=result.igv_rate.value, igv=t.igv.amount,
                   total_with_tax=t.total_with_tax.amount, margin_pct=t.margin.pct,
                   warnings=[t.margin.warning] if t.margin.warning else [], approval_required=result.approval.required,
                   approval_reasons=list(result.approval.reasons), quotation_validity_days=result.validity_days)


class QuotationOut(BaseModel):
    id: int
    ruc: str
    user_id: int
    status: str
    issued_on: date
    valid_until: date
    order_no: str | None
    lines: list[QuotationLineOut]
    discount_pct: JsonNumber
    subtotal: JsonNumber
    discount_amount: JsonNumber
    net: JsonNumber
    igv: JsonNumber
    total_with_tax: JsonNumber
    margin_pct: JsonNumber | None
    warnings: list[str]
    approval_required: bool
    approval_reasons: list[str]
    approval_confirmed: bool
    approval_note: str | None
    data_origin: Literal["estimated"] = "estimated"

    @classmethod
    def from_domain(cls, q: Quotation):
        return cls(id=q.id, ruc=q.ruc.value, user_id=q.user_id, status=q.status.value,
                   issued_on=q.issued_on, valid_until=q.valid_until, order_no=q.order_no,
                   lines=[QuotationLineOut.from_domain(x) for x in q.lines], discount_pct=q.discount.value,
                   subtotal=q.totals.subtotal.amount, discount_amount=q.totals.discount_amount.amount,
                   net=q.totals.net.amount, igv=q.totals.igv.amount, total_with_tax=q.totals.total_with_tax.amount,
                   margin_pct=q.totals.margin.pct,
                   warnings=[q.totals.margin.warning] if q.totals.margin.warning else [],
                   approval_required=q.approval.required, approval_reasons=list(q.approval.reasons),
                   approval_confirmed=q.approval.confirmed, approval_note=q.approval.note)


class QuotationPageOut(BaseModel):
    items: list[QuotationOut]
    total: int
    page: int
    per_page: int
