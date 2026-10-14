from app.core.domain import BusinessRuleError, ConflictError
from app.modules.auth.domain.entities import User

MIN_PASSWORD_LENGTH = 8


class PasswordPolicy:
    @staticmethod
    def check(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise BusinessRuleError(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.", "weak_password"
            )


class UserRules:
    @staticmethod
    def ensure_email_available(owner: User | None, user_id: int | None = None) -> None:
        """El correo es único: solo puede tenerlo el mismo usuario."""
        if owner is not None and owner.id != user_id:
            raise ConflictError("Ya existe un usuario con ese correo.", "email_taken")

    @staticmethod
    def ensure_salesperson_exists(salesperson_code: str | None, exists: bool) -> None:
        if salesperson_code is not None and not exists:
            raise BusinessRuleError(f"No existe el vendedor {salesperson_code}.", "unknown_salesperson")
