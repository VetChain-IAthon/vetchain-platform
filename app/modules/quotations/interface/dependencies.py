"""Cableado de cotizaciones."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.application import SessionUser
from app.core.auth import current_user
from app.core.database import get_db
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.quotations.application import use_cases as uc
from app.modules.quotations.infrastructure.gateways import CustomerPublicGateway, SettingsPublicGateway
from app.modules.quotations.infrastructure.repositories import SqlAlchemyQuotationRepository, SqlProductCatalog


def get_search_products(db: Session = Depends(get_db)) -> uc.SearchProducts:
    return uc.SearchProducts(SqlProductCatalog(db), SqlAlchemyUnitOfWork(session=db))


def get_get_product(db: Session = Depends(get_db)) -> uc.GetProduct:
    return uc.GetProduct(SqlProductCatalog(db), SqlAlchemyUnitOfWork(session=db))


def get_preview_quotation(db: Session = Depends(get_db), user: SessionUser = Depends(current_user)) -> uc.PreviewQuotation:
    return uc.PreviewQuotation(SqlProductCatalog(db), CustomerPublicGateway(user), SettingsPublicGateway(),
                               SqlAlchemyUnitOfWork(session=db))


def get_issue_quotation(db: Session = Depends(get_db), user: SessionUser = Depends(current_user)) -> uc.IssueQuotation:
    return uc.IssueQuotation(get_preview_quotation(db, user), SqlAlchemyQuotationRepository(db), SystemClock(),
                             SqlAlchemyUnitOfWork(session=db))


def get_list_quotations(db: Session = Depends(get_db)) -> uc.ListQuotations:
    return uc.ListQuotations(SqlAlchemyQuotationRepository(db), SqlAlchemyUnitOfWork(session=db))


def get_get_quotation(db: Session = Depends(get_db), user: SessionUser = Depends(current_user)) -> uc.GetQuotation:
    return uc.GetQuotation(SqlAlchemyQuotationRepository(db), CustomerPublicGateway(user),
                           SqlAlchemyUnitOfWork(session=db))
