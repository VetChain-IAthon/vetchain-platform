"""Cableado de customers: único lugar de la interfaz que ve la infraestructura."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.application import SessionUser
from app.core.domain import NotFoundError, Ruc
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.customers.application import use_cases as uc
from app.modules.customers.application import public
from app.modules.customers.infrastructure.gateways import SettingsPublicGateway
from app.modules.customers.infrastructure.repositories import SqlAlchemyContactRepository, SqlAlchemyCustomerReadRepository


def _customers(db: Session) -> SqlAlchemyCustomerReadRepository:
    return SqlAlchemyCustomerReadRepository(db)


def _uow(db: Session) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session=db)


def get_list_customers(db: Session = Depends(get_db)) -> uc.ListCustomers:
    return uc.ListCustomers(_customers(db), SettingsPublicGateway(), _uow(db))


def get_list_dormant_customers(db: Session = Depends(get_db)) -> uc.ListDormantCustomers:
    return uc.ListDormantCustomers(_customers(db), _uow(db))


def get_get_customer(db: Session = Depends(get_db)) -> uc.GetCustomer:
    return uc.GetCustomer(_customers(db), SettingsPublicGateway(), _uow(db))


def get_list_customer_orders(db: Session = Depends(get_db)) -> uc.ListCustomerOrders:
    return uc.ListCustomerOrders(_customers(db), _uow(db))


def get_list_customer_products(db: Session = Depends(get_db)) -> uc.ListCustomerProducts:
    return uc.ListCustomerProducts(_customers(db), _uow(db))


def get_get_commercial_terms(db: Session = Depends(get_db)) -> uc.GetCommercialTerms:
    return uc.GetCommercialTerms(_customers(db), SettingsPublicGateway(), _uow(db))


def get_list_contacts(db: Session = Depends(get_db)) -> uc.ListContacts:
    return uc.ListContacts(_customers(db), SqlAlchemyContactRepository(db), _uow(db))


def get_register_contact(db: Session = Depends(get_db)) -> uc.RegisterContact:
    return uc.RegisterContact(_customers(db), SqlAlchemyContactRepository(db), SystemClock(), _uow(db))


def get_build_whatsapp_link(db: Session = Depends(get_db)) -> uc.BuildWhatsappLink:
    return uc.BuildWhatsappLink(_customers(db), _uow(db))


def _public_commercial_terms(ruc: str, user: SessionUser) -> public.CommercialTerms:
    with SessionLocal() as db:
        result = uc.GetCommercialTerms(_customers(db), SettingsPublicGateway(), _uow(db)).execute(ruc, uc.scope_for(user))
    terms = result.terms
    return public.CommercialTerms(terms.level.value, terms.max_discount.value, terms.margin.value, terms.credit_days)


def _public_ensure_access(ruc: str, user: SessionUser) -> None:
    with SessionLocal() as db:
        customer = _customers(db).get(Ruc(ruc))
        if customer is None:
            raise NotFoundError("No existe un cliente con ese RUC.", "customer_not_found")
        uc.scope_for(user).ensure_includes(customer.salesperson_code)


public.configure(_public_commercial_terms, _public_ensure_access)
