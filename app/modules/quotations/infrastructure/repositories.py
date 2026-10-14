from __future__ import annotations

"""Lectura del catálogo Defontana y persistencia propia de cotizaciones."""
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.application import Page, Paging
from app.core.domain import DataOrigin, DateRange, Money, Ruc
from app.infrastructure.db.source_models import Customer as CustomerRow
from app.infrastructure.db.source_models import Order as OrderRow
from app.infrastructure.db.source_models import OrderLine as OrderLineRow
from app.infrastructure.db.source_models import Product as ProductRow
from app.modules.quotations.domain.entities import OrderRef, Product, Quotation, QuotationLine, QuotationTotals
from app.modules.quotations.domain.value_objects import ApprovalStatus, Margin, QuotationStatus, ReferencePrice
from app.modules.quotations.infrastructure.orm import QuotationLineRow, QuotationRow
from app.core.domain import Percentage


class SqlProductCatalog:
    def __init__(self, session: Session) -> None:
        self.session = session

    def search(self, text: str | None, family: str | None, paging: Paging) -> Page[Product]:
        filters = [ProductRow.is_core_product.is_(True), ProductRow.is_active.is_(True)]
        if text:
            filters.append(or_(ProductRow.name.ilike(f"%{text.strip()}%"), ProductRow.code.ilike(f"%{text.strip()}%")))
        if family:
            filters.append(ProductRow.category_code == family)
        total = self.session.scalar(select(func.count()).select_from(ProductRow).where(*filters)) or 0
        rows = self.session.scalars(select(ProductRow).where(*filters).order_by(ProductRow.name, ProductRow.code).offset(paging.offset).limit(paging.per_page))
        return Page.of([Product(row.code, row.name, row.category_code) for row in rows], total, paging)

    def get(self, code: str) -> Product | None:
        row = self.session.get(ProductRow, code)
        if row is None or not row.is_core_product or not row.is_active:
            return None
        return Product(row.code, row.name, row.category_code)

    def reference_prices(self, codes: list[str]) -> dict[str, ReferencePrice]:
        if not codes:
            return {}
        rows = self.session.execute(
            select(OrderLineRow, OrderRow)
            .join(OrderRow, OrderLineRow.order_no == OrderRow.order_no)
            .where(OrderLineRow.product_code.in_(codes), OrderLineRow.is_bonus.is_(False), OrderLineRow.quantity > 0,
                   or_(OrderRow.status_code.is_(None), OrderRow.status_code != "C"))
            .order_by(OrderRow.order_date.desc(), OrderRow.order_no.desc(), OrderLineRow.id.desc())
        )
        prices: dict[str, ReferencePrice] = {}
        for line, _order in rows:
            if line.product_code not in prices:
                prices[line.product_code] = ReferencePrice(Money(line.line_total / line.quantity), DataOrigin.ESTIMATED)
        return prices

    def unit_costs(self, codes: list[str]) -> dict[str, Money]:
        return {}  # Los archivos disponibles no contienen costos validados.


def _to_domain(row: QuotationRow) -> Quotation:
    lines = tuple(
        QuotationLine(line.product_code, line.quantity,
                      ReferencePrice(Money(line.unit_price), DataOrigin(line.price_origin)),
                      Money(line.unit_cost) if line.unit_cost is not None else None)
        for line in row.lines
    )
    totals = QuotationTotals(Money(row.subtotal), Money(row.discount_amount), Money(row.net), Money(row.igv),
                             Money(row.total_with_tax), Margin(row.margin_pct, None if row.margin_pct is not None else "no_cost_data"))
    approval = ApprovalStatus(row.approval_required, tuple(filter(None, row.approval_reasons.split(","))),
                              row.approval_confirmed, row.approval_note)
    return Quotation(Ruc(row.ruc), row.user_id, lines, Percentage(row.discount_pct), totals, approval,
                     row.issued_on, row.valid_until, QuotationStatus(row.status), row.order_no, row.id)


class SqlAlchemyQuotationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, quotation: Quotation) -> Quotation:
        row = QuotationRow(
            ruc=quotation.ruc.value, user_id=quotation.user_id, status=quotation.status.value,
            discount_pct=quotation.discount.value, subtotal=quotation.totals.subtotal.amount,
            discount_amount=quotation.totals.discount_amount.amount, net=quotation.totals.net.amount,
            igv=quotation.totals.igv.amount, total_with_tax=quotation.totals.total_with_tax.amount,
            margin_pct=quotation.totals.margin.pct, approval_required=quotation.approval.required,
            approval_reasons=",".join(quotation.approval.reasons), approval_confirmed=quotation.approval.confirmed,
            approval_note=quotation.approval.note, issued_on=quotation.issued_on, valid_until=quotation.valid_until,
            order_no=quotation.order_no,
            lines=[QuotationLineRow(product_code=line.product_code, quantity=line.quantity,
                                    unit_price=line.unit_price.price.amount, price_origin=line.unit_price.origin.value,
                                    unit_cost=line.unit_cost.amount if line.unit_cost else None) for line in quotation.lines],
        )
        self.session.add(row)
        self.session.flush()
        return _to_domain(row)

    def get(self, quotation_id: int) -> Quotation | None:
        row = self.session.get(QuotationRow, quotation_id)
        return _to_domain(row) if row else None

    def list(self, status: QuotationStatus | None, ruc: Ruc | None, date_range: DateRange | None,
             paging: Paging, salesperson_code: str | None = None) -> Page[Quotation]:
        filters = []
        if status:
            filters.append(QuotationRow.status == status.value)
        if ruc:
            filters.append(QuotationRow.ruc == ruc.value)
        if date_range:
            filters.extend((QuotationRow.issued_on >= date_range.from_date, QuotationRow.issued_on <= date_range.to_date))
        query = select(QuotationRow)
        if salesperson_code is not None:
            query = query.join(CustomerRow, QuotationRow.ruc == CustomerRow.ruc)
            filters.append(CustomerRow.salesperson_code == salesperson_code)
        query = query.where(*filters)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.scalars(query.order_by(QuotationRow.issued_on.desc(), QuotationRow.id.desc())
                                    .offset(paging.offset).limit(paging.per_page))
        return Page.of([_to_domain(row) for row in rows], total, paging)

    def list_issued(self) -> list[Quotation]:
        rows = self.session.scalars(select(QuotationRow).where(QuotationRow.status == QuotationStatus.ISSUED.value))
        return [_to_domain(row) for row in rows]

    def save(self, quotation: Quotation) -> None:
        row = self.session.get(QuotationRow, quotation.id)
        row.status = quotation.status.value
        row.order_no = quotation.order_no


class SqlOrderLookup:
    def __init__(self, session: Session) -> None:
        self.session = session

    def orders_since(self, since):
        rows = self.session.scalars(select(OrderRow).where(OrderRow.order_date >= since,
                             or_(OrderRow.status_code.is_(None), OrderRow.status_code != "C")))
        return [OrderRef(row.order_no, Ruc(row.ruc), row.order_date) for row in rows]
