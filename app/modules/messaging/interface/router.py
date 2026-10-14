from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.application import MANAGER, SALESPERSON, SessionUser
from app.core.auth import require_role
from app.core.config import settings
from app.core.database import get_db
from app.modules.messaging.application import use_cases as uc
from app.modules.messaging.interface import dependencies as deps
from app.modules.messaging.interface.schemas import EmailIn, EmailSentOut, EmailSetupOut, GmailAuthorizationOut, GmailConnectionOut, SenderIn, SenderOut
from app.modules.messaging.infrastructure import gmail_oauth

router = APIRouter(tags=["correo"])
manager = require_role(MANAGER)
any_role = require_role(MANAGER, SALESPERSON)


@router.get("/gmail/connection", response_model=GmailConnectionOut)
def gmail_connection(user: SessionUser = Depends(any_role), db: Session = Depends(get_db)):
    saved = gmail_oauth.connection(db, user.id)
    return {"available": gmail_oauth.configured(), "email": saved.email if saved else None}


@router.get("/gmail/connect", response_model=GmailAuthorizationOut)
def gmail_connect(return_path: str = Query("/reportes"), user: SessionUser = Depends(any_role),
                  db: Session = Depends(get_db)):
    return {"authorization_url": gmail_oauth.start(db, user.id, return_path)}


@router.get("/gmail/callback")
def gmail_callback(state: str, code: str, db: Session = Depends(get_db)):
    return_path = gmail_oauth.finish(db, state, code)
    return RedirectResponse(settings.frontend_url.rstrip("/") + return_path)


@router.delete("/gmail/connection", status_code=204)
def gmail_disconnect(user: SessionUser = Depends(any_role), db: Session = Depends(get_db)):
    gmail_oauth.disconnect(db, user.id)


@router.get("/email-senders", response_model=EmailSetupOut)
def list_senders(_: SessionUser = Depends(any_role), use_case: uc.ListSenders = Depends(deps.get_list_senders)):
    """Remitentes permitidos y si su proveedor está configurado."""
    return EmailSetupOut.from_result(use_case.execute())


@router.post("/email-senders", response_model=SenderOut, status_code=201)
def add_sender(body: SenderIn, _: SessionUser = Depends(manager), use_case: uc.AddSender = Depends(deps.get_add_sender)):
    """Agrega una cuenta Gmail o una dirección de un dominio verificado en Resend."""
    return SenderOut.from_domain(use_case.execute(uc.SenderCommand(body.name, body.address, body.is_default)))


@router.put("/email-senders/{sender_id}", response_model=SenderOut)
def update_sender(sender_id: int, body: SenderIn, _: SessionUser = Depends(manager),
                  use_case: uc.UpdateSender = Depends(deps.get_update_sender)):
    return SenderOut.from_domain(use_case.execute(sender_id, uc.SenderCommand(body.name, body.address, body.is_default)))


@router.delete("/email-senders/{sender_id}", status_code=204)
def delete_sender(sender_id: int, _: SessionUser = Depends(manager), use_case: uc.DeleteSender = Depends(deps.get_delete_sender)):
    use_case.execute(sender_id)


@router.post("/emails", response_model=EmailSentOut, status_code=201)
def send_email(body: EmailIn, user: SessionUser = Depends(any_role), use_case: uc.SendEmail = Depends(deps.get_send_email)):
    """Envía con Gmail o Resend desde un remitente permitido."""
    command = uc.SendEmailCommand(body.sender_id, body.to, body.subject, body.body, body.from_email, body.reply_to,
                                  [a.to_domain() for a in body.attachments])
    return EmailSentOut.from_result(use_case.execute(command, user))
