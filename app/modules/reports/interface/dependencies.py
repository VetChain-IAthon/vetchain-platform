"""Cableado HTTP de los repositorios de reportes."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.reports.application import use_cases as uc
from app.modules.reports.infrastructure.repositories import (
    SqlCustomersReadRepository, SqlSalesReadRepository, SqlStockReadRepository,
)


def _sales(db: Session) -> SqlSalesReadRepository:
    return SqlSalesReadRepository(db)


def _customers(db: Session) -> SqlCustomersReadRepository:
    return SqlCustomersReadRepository(db)


def _uow(db: Session) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session=db)


def get_dashboard_summary(db: Session = Depends(get_db)) -> uc.GetDashboardSummary:
    return uc.GetDashboardSummary(_sales(db), _customers(db), _uow(db))


def get_sales_report(db: Session = Depends(get_db)) -> uc.GetSalesReport:
    return uc.GetSalesReport(_sales(db), _uow(db))


def get_customers_report(db: Session = Depends(get_db)) -> uc.GetCustomersReport:
    return uc.GetCustomersReport(_sales(db), _customers(db), _uow(db))


def get_stock_report(db: Session = Depends(get_db)) -> uc.GetStockReport:
    return uc.GetStockReport(_sales(db), SqlStockReadRepository(db), _uow(db))


def get_salespeople_report(db: Session = Depends(get_db)) -> uc.GetSalespeopleReport:
    return uc.GetSalespeopleReport(_sales(db), _uow(db))


def get_receivables_report(db: Session = Depends(get_db)) -> uc.GetReceivablesReport:
    return uc.GetReceivablesReport(_sales(db), _uow(db))


def get_kpis(db: Session = Depends(get_db)) -> uc.GetKpis:
    return uc.GetKpis(get_dashboard_summary(db))


def get_funnel(db: Session = Depends(get_db)) -> uc.GetFunnelReport:
    return uc.GetFunnelReport(_sales(db), _uow(db))
