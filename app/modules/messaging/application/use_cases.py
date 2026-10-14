"""Casos de uso de messaging: remitentes permitidos y envío de correos."""
from dataclasses import dataclass, replace

from app.core.application import SessionUser
from app.core.domain import BusinessRuleError, Clock, NotFoundError, UnitOfWork
from app.modules.messaging.domain.entities import Attachment, DeliveryStatus, EmailLog, EmailSender, OutgoingEmail, require_own_domain
from app.modules.messaging.domain.ports import EmailGateway, EmailLogRepository, SenderRepository


@dataclass(frozen=True)
class EmailSetup:
    senders: list[EmailSender]
    provider_configured: bool


class ListSenders:
    def __init__(self, senders: SenderRepository, gateway: EmailGateway, uow: UnitOfWork) -> None:
        self.senders, self.gateway, self.uow = senders, gateway, uow

    def execute(self) -> EmailSetup:
        with self.uow:
            senders = self.senders.all()
            sender = next((item for item in senders if item.is_default), senders[0] if senders else None)
            return EmailSetup(senders, self.gateway.configured_for(sender.address) if sender else False)


@dataclass(frozen=True)
class SenderCommand:
    name: str
    address: str
    is_default: bool = False


def _clear_other_defaults(senders: SenderRepository, keep_id: int | None) -> None:
    for sender in senders.all():
        if sender.is_default and sender.id != keep_id:
            senders.save(replace(sender, is_default=False))


class AddSender:
    """Agrega un remitente. El primero queda por defecto; marcar otro por defecto desmarca al anterior."""

    def __init__(self, senders: SenderRepository, uow: UnitOfWork) -> None:
        self.senders, self.uow = senders, uow

    def execute(self, command: SenderCommand) -> EmailSender:
        sender = EmailSender(command.name, command.address, command.is_default)
        require_own_domain(sender.address)
        with self.uow:
            existing = self.senders.all()
            if any(s.address == sender.address for s in existing):
                raise BusinessRuleError("Ese remitente ya está en la lista.", "duplicate_sender")
            sender = replace(sender, is_default=sender.is_default or not existing)
            created = self.senders.add(sender)
            if created.is_default:
                _clear_other_defaults(self.senders, created.id)
            self.uow.commit()
            return created


class UpdateSender:
    def __init__(self, senders: SenderRepository, uow: UnitOfWork) -> None:
        self.senders, self.uow = senders, uow

    def execute(self, sender_id: int, command: SenderCommand) -> EmailSender:
        with self.uow:
            current = self._get(sender_id)
            updated = replace(EmailSender(command.name, command.address, command.is_default), id=current.id)
            require_own_domain(updated.address)
            if any(s.address == updated.address and s.id != sender_id for s in self.senders.all()):
                raise BusinessRuleError("Ese remitente ya está en la lista.", "duplicate_sender")
            self.senders.save(updated)
            if updated.is_default:
                _clear_other_defaults(self.senders, sender_id)
            self.uow.commit()
            return updated

    def _get(self, sender_id: int) -> EmailSender:
        found = self.senders.get(sender_id)
        if found is None:
            raise NotFoundError("No existe ese remitente.", "sender_not_found")
        return found


class DeleteSender:
    def __init__(self, senders: SenderRepository, uow: UnitOfWork) -> None:
        self.senders, self.uow = senders, uow

    def execute(self, sender_id: int) -> None:
        with self.uow:
            if self.senders.get(sender_id) is None:
                raise NotFoundError("No existe ese remitente.", "sender_not_found")
            self.senders.delete(sender_id)
            self.uow.commit()


@dataclass(frozen=True)
class SendEmailCommand:
    sender_id: int | None
    to: list[str]
    subject: str
    body: str
    from_email: str | None = None  # obligatorio si el remitente es un dominio
    reply_to: str | None = None
    attachments: list[Attachment] | None = None


@dataclass(frozen=True)
class SentEmail:
    log: EmailLog
    provider_configured: bool


class SendEmail:
    """Envía desde un remitente permitido. Sin clave de Resend se simula y queda registrado igual."""

    def __init__(self, senders: SenderRepository, logs: EmailLogRepository, gateway: EmailGateway, clock: Clock,
                 uow: UnitOfWork, personal_gmail=None) -> None:
        self.senders, self.logs, self.gateway, self.clock, self.uow = senders, logs, gateway, clock, uow
        self.personal_gmail = personal_gmail

    def execute(self, command: SendEmailCommand, user: SessionUser) -> SentEmail:
        with self.uow:
            sender = self.senders.get(command.sender_id) if command.sender_id is not None else None
            if command.sender_id is not None and sender is None:
                raise BusinessRuleError("Elige un remitente de la lista. Gerencia los define en Ajustes › Correo.", "sender_not_found")
            if sender is None and self.personal_gmail is None:
                raise BusinessRuleError("Conecta tu Gmail antes de enviar.", "gmail_connection_required")
            from_email = sender.resolve(command.from_email) if sender else self.personal_gmail.address(user.id)
            require_own_domain(from_email)
            email = OutgoingEmail(
                from_name=sender.name if sender else self.personal_gmail.name(user.id), from_email=from_email,
                to=tuple(t.strip().lower() for t in command.to if t.strip()), subject=command.subject.strip(),
                body=command.body.strip(), reply_to=(command.reply_to or "").strip().lower() or None,
                attachments=tuple(command.attachments or ()),
            )
            status, provider_id = self.gateway.send(email) if sender else self.personal_gmail.send(user.id, email)
            log = self.logs.add(EmailLog(user.id, email.from_email, email.to, email.subject, status, self.clock.now(),
                                         tuple(a.file_name for a in email.attachments), provider_id))
            self.uow.commit()
            return SentEmail(log, status is not DeliveryStatus.SIMULATED)
