"""Envío de correos con un remitente elegido de una lista que define gerencia (nunca fijo en el código).

Resend envía desde un dominio verificado y Gmail desde la cuenta autenticada. Un remitente
permitido aquí es una dirección exacta «ventas@mederi.pe» o un dominio «@mederi.pe».
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.core.domain import BusinessRuleError

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_DOMAIN = re.compile(r"^@[^\s@]+\.[^\s@]+$")
MAX_ATTACHMENTS_BYTES = 10 * 1024 * 1024
MAX_RECIPIENTS = 10
GMAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com"})
PUBLIC_EMAIL_DOMAINS = frozenset({
    "hotmail.com", "outlook.com", "live.com", "msn.com",
    "yahoo.com", "yahoo.es", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com",
})


def is_email(value: str) -> bool:
    return bool(_EMAIL.match(value))


def require_own_domain(address: str) -> None:
    """Los buzones públicos sin un proveedor configurado no son remitentes admitidos."""
    domain = address.strip().lower().rsplit("@", 1)[-1]
    if domain in PUBLIC_EMAIL_DOMAINS:
        raise BusinessRuleError(
            f"{domain} es un dominio público. Usa un correo de un dominio propio verificado en Resend como origen.",
            "sender_public_domain",
        )


def is_gmail_sender(address: str) -> bool:
    return address.strip().lower().rsplit("@", 1)[-1] in GMAIL_DOMAINS


@dataclass(frozen=True)
class EmailSender:
    name: str  # nombre que ve el cliente, por ejemplo «Mederi Pharma»
    address: str  # «ventas@mederi.pe» (dirección exacta) o «@mederi.pe» (todo el dominio)
    is_default: bool = False
    id: int | None = None

    def __post_init__(self) -> None:
        name, address = self.name.strip(), self.address.strip().lower()
        if not name:
            raise BusinessRuleError("Escribe el nombre que verá quien recibe el correo.", "missing_sender_name")
        if not (_EMAIL.match(address) or _DOMAIN.match(address)):
            raise BusinessRuleError("Escribe un correo (ventas@mederi.pe) o un dominio que empiece con @ (@mederi.pe).",
                                    "invalid_sender_address")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "address", address)

    @property
    def is_domain(self) -> bool:
        return self.address.startswith("@")

    def resolve(self, from_email: str | None) -> str:
        """Dirección de origen final. Con un dominio se elige la dirección; con una exacta no se puede cambiar."""
        if not self.is_domain:
            if from_email and from_email.strip().lower() != self.address:
                raise BusinessRuleError("Este remitente solo puede enviar desde su propia dirección.", "sender_mismatch")
            return self.address
        email = (from_email or "").strip().lower()
        if not _EMAIL.match(email) or not email.endswith(self.address):
            raise BusinessRuleError(f"La dirección de origen debe terminar en {self.address}.", "sender_mismatch")
        return email


@dataclass(frozen=True)
class Attachment:
    file_name: str
    content: bytes
    content_type: str = "application/pdf"


@dataclass(frozen=True)
class OutgoingEmail:
    from_name: str
    from_email: str
    to: tuple[str, ...]
    subject: str
    body: str
    reply_to: str | None = None
    attachments: tuple[Attachment, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.to:
            raise BusinessRuleError("Escribe al menos un destinatario.", "missing_recipient")
        if len(self.to) > MAX_RECIPIENTS:
            raise BusinessRuleError(f"Se puede enviar a {MAX_RECIPIENTS} destinatarios como máximo.", "too_many_recipients")
        bad = [email for email in self.to + ((self.reply_to,) if self.reply_to else ()) if not _EMAIL.match(email)]
        if bad:
            raise BusinessRuleError(f"Correo no válido: {bad[0]}. Revisa que tenga la forma nombre@empresa.pe.", "invalid_recipient")
        if not self.subject.strip():
            raise BusinessRuleError("Escribe el asunto del correo.", "missing_subject")
        if not self.body.strip():
            raise BusinessRuleError("Escribe el mensaje del correo.", "missing_body")
        if sum(len(a.content) for a in self.attachments) > MAX_ATTACHMENTS_BYTES:
            raise BusinessRuleError("Los adjuntos pesan más de 10 MB.", "attachments_too_large")


class DeliveryStatus(StrEnum):
    SENT = "sent"  # el proveedor aceptó el correo
    SIMULATED = "simulated"  # sin RESEND_API_KEY: se registra pero no sale


@dataclass(frozen=True)
class EmailLog:
    """Registro de cada envío: quién, desde qué dirección, a quién, cuándo y con qué resultado."""

    user_id: int
    from_email: str
    to: tuple[str, ...]
    subject: str
    status: DeliveryStatus
    created_at: datetime
    attachment_names: tuple[str, ...] = ()
    provider_message_id: str | None = None
    id: int | None = None
