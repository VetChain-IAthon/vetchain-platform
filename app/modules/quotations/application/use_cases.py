"""Cada operación de cotizaciones usa un único caso de uso."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.application import Page, Paging, SessionUser
from app.core.domain import BusinessRuleError, Clock, DateRange, ForbiddenError, NotFoundError, Percentage, Ruc, UnitOfWork
from app.modules.quotations.domain.entities import Product, Quotation, QuotationLine, QuotationTotals
from app.modules.quotations.domain.ports import CustomerTermsGateway, ProductCatalog, QuotationRepository, SettingsGateway
from app.modules.quotations.domain.services import ApprovalPolicy, QuotationPricer
from app.modules.quotations.domain.value_objects import ApprovalStatus, QuotationStatus, ReferencePrice


@dataclass(frozen=True)
class ProductInfo:
    product: Product
    reference_price: ReferencePrice | None


class SearchProducts:
    def __init__(self, catalog: ProductCatalog, uow: UnitOfWork) -> None:
        self.catalog, self.uow = catalog, uow

    def execute(self, search: str | None, family: str | None, paging: Paging) -> Page[ProductInfo]:
        with self.uow:
            page = self.catalog.search(search, family, paging)
            prices = self.catalog.reference_prices([item.code for item in page.items])
            return Page.of([ProductInfo(item, prices.get(item.code)) for item in page.items], page.total, paging)


class GetProduct:
    def __init__(self, catalog: ProductCatalog, uow: UnitOfWork) -> None:
        self.catalog, self.uow = catalog, uow

    def execute(self, code: str) -> ProductInfo:
        with self.uow:
            product = self.catalog.get(code)
            if product is None:
                raise NotFoundError("No existe un producto veterinario activo con ese código.", "product_not_found")
            return ProductInfo(product, self.catalog.reference_prices([code]).get(code))


@dataclass(frozen=True)
class LineInput:
    product_code: str
    quantity: Decimal


@dataclass(frozen=True)
class QuotationInput:
    ruc: str
    lines: tuple[LineInput, ...]
    discount_pct: Decimal


@dataclass(frozen=True)
class QuotationPreview:
    ruc: str
    lines: tuple[QuotationLine, ...]
    discount: Percentage
    totals: QuotationTotals
    approval: ApprovalStatus
    igv_rate: Percentage
    validity_days: int
    level: str
    credit_days: int
    max_discount: Percentage


class PreviewQuotation:
    def __init__(self, catalog: ProductCatalog, customers: CustomerTermsGateway,
                 settings: SettingsGateway, uow: UnitOfWork) -> None:
        self.catalog, self.customers, self.settings, self.uow = catalog, customers, settings, uow

    def execute(self, data: QuotationInput) -> QuotationPreview:
        with self.uow:
            if not data.lines:
                raise BusinessRuleError("Agrega al menos un producto a la cotización.", "empty_quotation")
            codes = [line.product_code for line in data.lines]
            if len(codes) != len(set(codes)):
                raise BusinessRuleError("Un producto no puede repetirse en la cotización.", "duplicated_product")
            terms = self.customers.terms_for(Ruc(data.ruc))
            pricing = self.settings.pricing_terms()
            discount = Percentage(data.discount_pct)
            references = self.catalog.reference_prices(codes)
            costs = self.catalog.unit_costs(codes)
            lines: list[QuotationLine] = []
            for item in data.lines:
                if self.catalog.get(item.product_code) is None:
                    raise NotFoundError("Uno de los productos no existe o no es veterinario activo.", "product_not_found")
                reference = references.get(item.product_code)
                if reference is None:
                    raise BusinessRuleError("Un producto no tiene un precio pagado de referencia. No se puede cotizar aún.",
                                            "reference_price_unavailable")
                lines.append(QuotationLine(item.product_code, item.quantity, reference, costs.get(item.product_code)))
            totals = QuotationPricer(pricing.igv_rate).price(lines, discount)
            approval = ApprovalPolicy(terms.max_discount, pricing.min_margin).evaluate(discount, totals.margin)
            return QuotationPreview(data.ruc, tuple(lines), discount, totals, approval, pricing.igv_rate,
                                    pricing.quotation_validity_days, terms.level.value, terms.credit_days,
                                    terms.max_discount)


@dataclass(frozen=True)
class IssueQuotationCommand:
    quotation: QuotationInput
    approval_confirmed: bool = False
    approval_note: str | None = None


class IssueQuotation:
    def __init__(self, preview: PreviewQuotation, quotations: QuotationRepository,
                 clock: Clock, uow: UnitOfWork) -> None:
        self.preview, self.quotations, self.clock, self.uow = preview, quotations, clock, uow

    def execute(self, command: IssueQuotationCommand, user: SessionUser) -> Quotation:
        result = self.preview.execute(command.quotation)  # Recalcula precios y reglas al emitir.
        approval = result.approval
        if approval.required and command.approval_confirmed:
            if not user.is_manager:
                raise ForbiddenError("Solo gerencia puede confirmar la aprobación.", "manager_approval_required")
            if not (command.approval_note or "").strip():
                raise BusinessRuleError("Escribe una nota para confirmar la aprobación.", "approval_note_required")
            approval = approval.confirm(command.approval_note)
        with self.uow:
            quotation = Quotation.issue(Ruc(result.ruc), user.id, result.lines, result.discount,
                                        result.totals, approval, self.clock.today(), result.validity_days)
            quotation = self.quotations.add(quotation)
            self.uow.commit()
            return quotation


class ListQuotations:
    def __init__(self, quotations: QuotationRepository, uow: UnitOfWork) -> None:
        self.quotations, self.uow = quotations, uow

    def execute(self, user: SessionUser, status: QuotationStatus | None, ruc: str | None,
                date_range: DateRange | None, paging: Paging) -> Page[Quotation]:
        if not user.is_manager and not user.salesperson_code:
            raise ForbiddenError("El vendedor no tiene una cartera asignada.", "salesperson_code_required")
        with self.uow:
            return self.quotations.list(status, Ruc(ruc) if ruc else None, date_range, paging,
                                        None if user.is_manager else user.salesperson_code)


class GetQuotation:
    def __init__(self, quotations: QuotationRepository, customers: CustomerTermsGateway, uow: UnitOfWork) -> None:
        self.quotations, self.customers, self.uow = quotations, customers, uow

    def execute(self, quotation_id: int) -> Quotation:
        with self.uow:
            quotation = self.quotations.get(quotation_id)
            if quotation is None:
                raise NotFoundError("No existe esa cotización.", "quotation_not_found")
            self.customers.ensure_access(quotation.ruc)
            return quotation
