"""Remitentes, registro de envíos y entrega mediante Resend o Gmail."""
import base64
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.domain import BusinessRuleError
from app.modules.messaging.domain.entities import DeliveryStatus, EmailLog, EmailSender, OutgoingEmail, is_gmail_sender
from app.modules.messaging.infrastructure.orm import EmailLogRow, EmailSenderRow


def _sender(row: EmailSenderRow) -> EmailSender:
    return EmailSender(row.name, row.address, row.is_default, row.id)


class SqlSenderRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def all(self) -> list[EmailSender]:
        rows = self._session.scalars(select(EmailSenderRow).order_by(EmailSenderRow.is_default.desc(), EmailSenderRow.name))
        return [_sender(row) for row in rows]

    def get(self, sender_id: int) -> EmailSender | None:
        row = self._session.get(EmailSenderRow, sender_id)
        return None if row is None else _sender(row)

    def add(self, sender: EmailSender) -> EmailSender:
        row = EmailSenderRow(name=sender.name, address=sender.address, is_default=sender.is_default)
        self._session.add(row)
        self._session.flush()
        return _sender(row)

    def save(self, sender: EmailSender) -> None:
        row = self._session.get(EmailSenderRow, sender.id)
        row.name, row.address, row.is_default = sender.name, sender.address, sender.is_default
        self._session.flush()

    def delete(self, sender_id: int) -> None:
        self._session.delete(self._session.get(EmailSenderRow, sender_id))


class SqlEmailLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, log: EmailLog) -> EmailLog:
        row = EmailLogRow(user_id=log.user_id, from_email=log.from_email, recipients=",".join(log.to), subject=log.subject[:300],
                          status=log.status.value, attachment_names=",".join(log.attachment_names),
                          provider_message_id=log.provider_message_id, created_at=log.created_at)
        self._session.add(row)
        self._session.flush()
        return EmailLog(log.user_id, log.from_email, log.to, log.subject, log.status, log.created_at, log.attachment_names,
                        log.provider_message_id, row.id)


RESEND_URL = "https://api.resend.com/emails"


class ResendGateway:
    """Envía por Resend. Sin clave, simula el envío para desarrollo y pruebas."""

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._api_key = api_key.strip()
        self._client = client

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def configured_for(self, _address: str) -> bool:
        return self.configured

    def send(self, email: OutgoingEmail) -> tuple[DeliveryStatus, str | None]:
        if not self.configured:
            return DeliveryStatus.SIMULATED, None
        payload = {
            "from": f"{email.from_name} <{email.from_email}>",
            "to": list(email.to),
            "subject": email.subject,
            "text": email.body,
        }
        if email.reply_to:
            payload["reply_to"] = email.reply_to
        if email.attachments:
            payload["attachments"] = [
                {"content": base64.b64encode(a.content).decode("ascii"), "filename": a.file_name}
                for a in email.attachments
            ]
        client = self._client or httpx.Client(timeout=20)
        try:
            response = client.post(RESEND_URL, json=payload, headers={"Authorization": f"Bearer {self._api_key}"})
        except httpx.HTTPError:
            raise BusinessRuleError("No se pudo conectar con Resend. Intenta de nuevo en unos minutos.", "email_provider_unavailable") from None
        finally:
            if self._client is None:
                client.close()
        if response.status_code == 200:
            try:
                provider_id = response.json().get("id")
            except ValueError:
                provider_id = None
            if provider_id:
                return DeliveryStatus.SENT, provider_id
            raise BusinessRuleError("Resend no confirmó el envío. Intenta de nuevo.", "email_provider_unavailable")
        if response.status_code == 403:
            raise BusinessRuleError("Resend rechazó el remitente. Usa un dominio propio verificado en Resend y permitido para esta clave de envío.",
                                    "sender_not_verified")
        raise BusinessRuleError(f"Resend no aceptó el correo ({response.status_code}). Revisa los datos y la configuración del dominio.", "email_rejected")


class GmailSmtpGateway:
    """Envía desde una única cuenta Gmail autenticada mediante contraseña de aplicación."""

    def __init__(self, account: str, app_password: str) -> None:
        self._account = account.strip().lower()
        self._app_password = app_password.replace(" ", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self._account and self._app_password)

    def configured_for(self, address: str) -> bool:
        return self.configured and address.strip().lower() == self._account

    def send(self, email: OutgoingEmail) -> tuple[DeliveryStatus, str | None]:
        if not self.configured:
            raise BusinessRuleError(
                "Para enviar desde Gmail, configura GMAIL_SMTP_EMAIL y GMAIL_SMTP_APP_PASSWORD en el servidor.",
                "gmail_not_configured",
            )
        if email.from_email.lower() != self._account:
            raise BusinessRuleError(
                "El correo de origen debe coincidir con la cuenta configurada en GMAIL_SMTP_EMAIL.",
                "gmail_sender_mismatch",
            )
        message = EmailMessage()
        message["From"] = formataddr((email.from_name, self._account))
        message["To"] = ", ".join(email.to)
        message["Subject"] = email.subject
        if email.reply_to:
            message["Reply-To"] = email.reply_to
        message_id = make_msgid()
        message["Message-ID"] = message_id
        message.set_content(email.body)
        for attachment in email.attachments:
            main_type, _, sub_type = attachment.content_type.partition("/")
            message.add_attachment(attachment.content, maintype=main_type or "application",
                                   subtype=sub_type or "octet-stream", filename=attachment.file_name)
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=20) as smtp:
                smtp.login(self._account, self._app_password)
                refused = smtp.send_message(message, from_addr=self._account, to_addrs=list(email.to))
                if refused:
                    raise BusinessRuleError("Gmail rechazó uno o más destinatarios.", "gmail_recipient_rejected")
        except smtplib.SMTPAuthenticationError:
            raise BusinessRuleError(
                "Gmail rechazó el acceso. Revisa la cuenta y su contraseña de aplicación.", "gmail_auth_failed",
            ) from None
        except (smtplib.SMTPException, OSError):
            raise BusinessRuleError(
                "No se pudo enviar por Gmail. Revisa la conexión y vuelve a intentar.", "gmail_unavailable",
            ) from None
        return DeliveryStatus.SENT, message_id


class RoutingEmailGateway:
    """Gmail para cuentas autenticadas; Resend para dominios propios."""

    def __init__(self, resend: ResendGateway, gmail: GmailSmtpGateway) -> None:
        self._resend, self._gmail = resend, gmail

    @property
    def configured(self) -> bool:
        return self._resend.configured or self._gmail.configured

    def configured_for(self, address: str) -> bool:
        gateway = self._gmail if is_gmail_sender(address) else self._resend
        return gateway.configured_for(address)

    def send(self, email: OutgoingEmail) -> tuple[DeliveryStatus, str | None]:
        gateway = self._gmail if is_gmail_sender(email.from_email) else self._resend
        return gateway.send(email)
