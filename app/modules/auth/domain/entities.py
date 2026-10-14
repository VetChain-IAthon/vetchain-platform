from dataclasses import dataclass

from app.core.domain import BusinessRuleError, ConflictError
from app.modules.auth.domain.value_objects import CurrentUser, Email, Role


def _clean(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None


@dataclass
class User:
    """Reglas: un salesperson tiene salesperson_code; un usuario inactivo no inicia sesión.
    El correo único lo garantiza el repositorio (ConflictError al crear)."""

    email: Email
    full_name: str
    role: Role
    password_hash: str
    phone: str | None = None
    salesperson_code: str | None = None
    active: bool = True
    id: int | None = None

    def __post_init__(self) -> None:
        full_name = _clean(self.full_name)
        if full_name is None:
            raise BusinessRuleError("El nombre completo es obligatorio.", "missing_full_name")
        self.full_name = full_name
        self.phone = _clean(self.phone)
        self.salesperson_code = _clean(self.salesperson_code)
        self._check_role(self.role, self.salesperson_code)

    @staticmethod
    def _check_role(role: Role, salesperson_code: str | None) -> None:
        if role is Role.SALESPERSON and salesperson_code is None:
            raise BusinessRuleError("Un vendedor debe tener código de vendedor.", "missing_salesperson_code")

    def can_log_in(self) -> bool:
        return self.active

    def update_profile(self, email: Email, phone: str | None) -> None:
        """El propio usuario solo cambia su correo y su teléfono."""
        self.email = email
        self.phone = _clean(phone)

    def change_role(self, role: Role, salesperson_code: str | None) -> None:
        salesperson_code = _clean(salesperson_code)
        self._check_role(role, salesperson_code)
        self.role = role
        self.salesperson_code = salesperson_code

    def deactivate(self, by: CurrentUser) -> None:
        if by.id == self.id:
            raise ConflictError("No puedes desactivar tu propia cuenta.", "self_deactivation")
        self.active = False

    def activate(self) -> None:
        self.active = True

    def to_current_user(self) -> CurrentUser:
        if self.id is None:
            raise ValueError("El usuario aún no está guardado.")
        return CurrentUser(self.id, self.role, self.salesperson_code)
