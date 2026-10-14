"""Rutas HTTP de productos y cotizaciones."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.core.application import MANAGER, SALESPERSON, Paging, SessionUser
from app.core.auth import require_role
from app.core.domain import BusinessRuleError, DateRange
from app.modules.quotations.application import use_cases as uc
from app.modules.quotations.domain.value_objects import QuotationStatus
from app.modules.quotations.interface import dependencies as deps
from app.modules.quotations.interface.schemas import (
    ProductOut, ProductPageOut, QuotationIssueIn, QuotationOut, QuotationPageOut,
    QuotationPreviewIn, QuotationPreviewOut,
)

router = APIRouter(tags=["cotizaciones"])
any_role = require_role(MANAGER, SALESPERSON)


@router.get("/products", response_model=ProductPageOut)
def search_products(search: str | None = Query(None, max_length=100), family: str | None = Query(None, max_length=3),
                    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                    _: SessionUser = Depends(any_role), use_case: uc.SearchProducts = Depends(deps.get_search_products)):
    result = use_case.execute(search, family, Paging(page, per_page))
    return ProductPageOut(items=[ProductOut.from_result(item) for item in result.items],
                          total=result.total, page=result.page, per_page=result.per_page)


@router.get("/products/{code}", response_model=ProductOut)
def get_product(code: str, _: SessionUser = Depends(any_role),
                use_case: uc.GetProduct = Depends(deps.get_get_product)):
    return ProductOut.from_result(use_case.execute(code))


@router.post("/quotation-previews", response_model=QuotationPreviewOut)
def preview_quotation(body: QuotationPreviewIn, _: SessionUser = Depends(any_role),
                      use_case: uc.PreviewQuotation = Depends(deps.get_preview_quotation)):
    return QuotationPreviewOut.from_result(use_case.execute(body.to_command()))


@router.get("/quotations", response_model=QuotationPageOut)
def list_quotations(status: Literal["issued", "converted", "expired"] | None = None,
                    ruc: str | None = None, from_date: date | None = Query(None, alias="from"),
                    to_date: date | None = Query(None, alias="to"), page: int = Query(1, ge=1),
                    per_page: int = Query(20, ge=1, le=100), user: SessionUser = Depends(any_role),
                    use_case: uc.ListQuotations = Depends(deps.get_list_quotations)):
    if (from_date is None) != (to_date is None):
        raise BusinessRuleError("Indica ambas fechas, desde y hasta.", "incomplete_date_range")
    period = DateRange(from_date, to_date) if from_date and to_date else None
    result = use_case.execute(user, QuotationStatus(status) if status else None, ruc, period, Paging(page, per_page))
    return QuotationPageOut(items=[QuotationOut.from_domain(item) for item in result.items],
                            total=result.total, page=result.page, per_page=result.per_page)


@router.post("/quotations", response_model=QuotationOut, status_code=201)
def issue_quotation(body: QuotationIssueIn, user: SessionUser = Depends(any_role),
                    use_case: uc.IssueQuotation = Depends(deps.get_issue_quotation)):
    command = uc.IssueQuotationCommand(body.to_command(), body.approval_confirmed, body.approval_note)
    return QuotationOut.from_domain(use_case.execute(command, user))


@router.get("/quotations/{quotation_id}", response_model=QuotationOut)
def get_quotation(quotation_id: int, _: SessionUser = Depends(any_role),
                  use_case: uc.GetQuotation = Depends(deps.get_get_quotation)):
    return QuotationOut.from_domain(use_case.execute(quotation_id))
