import re
from dataclasses import dataclass
from enum import StrEnum

from app.core.domain import BusinessRuleError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Role(StrEnum):
    MANAGER = "manager"
    SALESPERSON = "salesperson"


@dataclass(frozen=True)
class Email:
    """Correo normalizado en minúsculas."""

    value: str

    def __post_init__(self) -> None:
        value = str(self.value).strip().lower()
        if not _EMAIL.match(value):
            raise BusinessRuleError("El correo no es válido.", "invalid_email")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CurrentUser:
    """Usuario de la sesión, con lo justo para autorizar."""

    id: int
    role: Role
    salesperson_code: str | None

    @property
    def is_manager(self) -> bool:
        return self.role is Role.MANAGER
