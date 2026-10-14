"""Nueve rutas de consulta de gerencia para el Panel y Reportes."""
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.application import MANAGER
from app.core.auth import require_role
from app.modules.reports.application import use_cases as uc
from app.modules.reports.interface import dependencies as deps
from app.modules.reports.interface.schemas import (
    DashboardSummaryOut, CustomersReportOut, FunnelReportOut, KpiOut, KpiReportOut,
    PeriodOut, ReceivablesReportOut, ReportCatalogOut, ReportEntryOut, SalesReportOut,
    SalespeopleReportOut, StockReportOut,
)

router = APIRouter(tags=["panel y reportes"], dependencies=[Depends(require_role(MANAGER))])


def _query(date_from: date | None, date_to: date | None) -> uc.ReportQuery:
    return uc.ReportQuery(date_from, date_to)


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    use_case: uc.GetDashboardSummary = Depends(deps.get_dashboard_summary),
):
    return DashboardSummaryOut.from_domain(use_case.execute(_query(date_from, date_to)))


@router.get("/reports", response_model=ReportCatalogOut)
def list_reports():
    items = uc.ListReports().execute()
    return ReportCatalogOut(items=[ReportEntryOut(code=x.code, name=x.name, path=x.path,
                                                  data_origin=x.data_origin.value if x.data_origin else None,
                                                  warning=x.warning) for x in items], total=len(items))


@router.get("/reports/kpis", response_model=KpiReportOut)
def get_kpis(
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    use_case: uc.GetKpis = Depends(deps.get_kpis),
):
    result = use_case.execute(_query(date_from, date_to))
    return KpiReportOut(period=PeriodOut.from_domain(result.period),
                        items=[KpiOut(code=x.code, value=x.value, target=x.target,
                                      status=x.status.value if x.status else None,
                                      data_origin=x.data_origin.value, warning=x.warning) for x in result.items],
                        warnings=result.warnings)


@router.get("/reports/sales", response_model=SalesReportOut)
def get_sales_report(
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    use_case: uc.GetSalesReport = Depends(deps.get_sales_report),
):
    return SalesReportOut.from_domain(use_case.execute(_query(date_from, date_to)))


@router.get("/reports/customers", response_model=CustomersReportOut)
def get_customers_report(
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    use_case: uc.GetCustomersReport = Depends(deps.get_customers_report),
):
    return CustomersReportOut.from_domain(use_case.execute(_query(date_from, date_to)))


@router.get("/reports/stock", response_model=StockReportOut)
def get_stock_report(
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    use_case: uc.GetStockReport = Depends(deps.get_stock_report),
):
    return StockReportOut.from_domain(use_case.execute(_query(date_from, date_to)))


@router.get("/reports/receivables", response_model=ReceivablesReportOut)
def get_receivables_report(
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    use_case: uc.GetReceivablesReport = Depends(deps.get_receivables_report),
):
    return ReceivablesReportOut(period=PeriodOut.from_domain(use_case.execute(_query(date_from, date_to))))


@router.get("/reports/salespeople", response_model=SalespeopleReportOut)
def get_salespeople_report(
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    use_case: uc.GetSalespeopleReport = Depends(deps.get_salespeople_report),
):
    return SalespeopleReportOut.from_domain(use_case.execute(_query(date_from, date_to)))


@router.get("/reports/funnel", response_model=FunnelReportOut)
def get_funnel_report(
    date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
    use_case: uc.GetFunnelReport = Depends(deps.get_funnel),
):
    return FunnelReportOut(period=PeriodOut.from_domain(use_case.execute(_query(date_from, date_to))))
