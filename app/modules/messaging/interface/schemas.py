import base64
import binascii

from pydantic import BaseModel, Field, field_validator

from app.modules.messaging.application import use_cases as uc
from app.modules.messaging.domain.entities import Attachment, EmailSender


class SenderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120, description="Nombre que ve quien recibe, por ejemplo «Mederi Pharma»")
    address: str = Field(min_length=3, max_length=200, description="ventas@mederi.pe (dirección verificada) o @mederi.pe (dominio autenticado)")
    is_default: bool = False


class SenderOut(BaseModel):
    id: int
    name: str
    address: str
    is_domain: bool = Field(description="True: se puede enviar desde cualquier dirección de ese dominio")
    is_default: bool

    @classmethod
    def from_domain(cls, sender: EmailSender) -> "SenderOut":
        return cls(id=sender.id, name=sender.name, address=sender.address, is_domain=sender.is_domain, is_default=sender.is_default)


class EmailSetupOut(BaseModel):
    senders: list[SenderOut]
    provider_configured: bool = Field(description="True si el proveedor del remitente predeterminado está configurado")

    @classmethod
    def from_result(cls, setup: uc.EmailSetup) -> "EmailSetupOut":
        return cls(senders=[SenderOut.from_domain(s) for s in setup.senders], provider_configured=setup.provider_configured)


class GmailConnectionOut(BaseModel):
    available: bool
    email: str | None


class GmailAuthorizationOut(BaseModel):
    authorization_url: str


class AttachmentIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=200)
    content_base64: str
    content_type: str = "application/pdf"

    @field_validator("content_base64")
    @classmethod
    def _decodable(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("El adjunto no está en base64.") from None
        return value

    def to_domain(self) -> Attachment:
        return Attachment(self.file_name, base64.b64decode(self.content_base64), self.content_type)


class EmailIn(BaseModel):
    sender_id: int | None = Field(None, description="Vacío: enviar desde la cuenta Gmail conectada por este usuario")
    from_email: str | None = Field(None, description="Obligatorio si el remitente es un dominio (@mederi.pe)")
    to: list[str] = Field(min_length=1, max_length=10)
    reply_to: str | None = None
    subject: str = Field(max_length=300)
    body: str = Field(max_length=20000)
    attachments: list[AttachmentIn] = Field(default_factory=list, max_length=5)


class EmailSentOut(BaseModel):
    id: int
    status: str = Field(description="sent (el proveedor lo aceptó) o simulated (sin clave de Resend)")
    from_email: str
    to: list[str]

    @classmethod
    def from_result(cls, result: uc.SentEmail) -> "EmailSentOut":
        log = result.log
        return cls(id=log.id, status=log.status.value, from_email=log.from_email, to=list(log.to))
