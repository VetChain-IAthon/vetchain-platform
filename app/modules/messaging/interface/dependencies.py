"""Cableado de messaging: único lugar de la interfaz que ve la infraestructura."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.messaging.application import use_cases as uc
from app.modules.messaging.infrastructure.repositories import GmailSmtpGateway, ResendGateway, RoutingEmailGateway, SqlEmailLogRepository, SqlSenderRepository
from app.modules.messaging.infrastructure.gmail_oauth import GmailOAuthGateway


def get_gateway() -> RoutingEmailGateway:
    return RoutingEmailGateway(
        ResendGateway(settings.resend_api_key),
        GmailSmtpGateway(settings.gmail_smtp_email, settings.gmail_smtp_app_password),
    )


def _uow(db: Session) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session=db)


def get_list_senders(db: Session = Depends(get_db), gateway: RoutingEmailGateway = Depends(get_gateway)) -> uc.ListSenders:
    return uc.ListSenders(SqlSenderRepository(db), gateway, _uow(db))


def get_add_sender(db: Session = Depends(get_db)) -> uc.AddSender:
    return uc.AddSender(SqlSenderRepository(db), _uow(db))


def get_update_sender(db: Session = Depends(get_db)) -> uc.UpdateSender:
    return uc.UpdateSender(SqlSenderRepository(db), _uow(db))


def get_delete_sender(db: Session = Depends(get_db)) -> uc.DeleteSender:
    return uc.DeleteSender(SqlSenderRepository(db), _uow(db))


def get_send_email(db: Session = Depends(get_db), gateway: RoutingEmailGateway = Depends(get_gateway)) -> uc.SendEmail:
    return uc.SendEmail(SqlSenderRepository(db), SqlEmailLogRepository(db), gateway, SystemClock(), _uow(db), GmailOAuthGateway(db))
