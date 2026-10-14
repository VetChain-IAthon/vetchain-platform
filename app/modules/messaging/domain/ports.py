from typing import Protocol

from app.modules.messaging.domain.entities import DeliveryStatus, EmailLog, EmailSender, OutgoingEmail


class SenderRepository(Protocol):
    def all(self) -> list[EmailSender]: ...

    def get(self, sender_id: int) -> EmailSender | None: ...

    def add(self, sender: EmailSender) -> EmailSender: ...

    def save(self, sender: EmailSender) -> None: ...

    def delete(self, sender_id: int) -> None: ...


class EmailLogRepository(Protocol):
    def add(self, log: EmailLog) -> EmailLog: ...


class EmailGateway(Protocol):
    @property
    def configured(self) -> bool:
        """True si hay al menos un proveedor configurado."""
        ...

    def configured_for(self, address: str) -> bool:
        """True si el proveedor del remitente indicado está listo."""
        ...

    def send(self, email: OutgoingEmail) -> tuple[DeliveryStatus, str | None]:
        """(estado, id del mensaje en el proveedor). BusinessRuleError si el proveedor lo rechaza."""
        ...
