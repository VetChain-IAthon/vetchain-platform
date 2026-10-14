"""Errores de negocio. La interfaz los traduce a códigos HTTP (ver app/core/errors.py); el dominio no habla de HTTP."""


class DomainError(Exception):
    """Base de los errores de negocio. `code` es estable (inglés) y `message` va al usuario (español)."""

    code = "domain_error"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class BusinessRuleError(DomainError):
    """Se rompe una regla del negocio (400)."""

    code = "business_rule"


class NotFoundError(DomainError):
    """No existe lo que se pidió (404)."""

    code = "not_found"


class ForbiddenError(DomainError):
    """El usuario no puede hacer esto o no es de su cartera (403)."""

    code = "forbidden"


class ConflictError(DomainError):
    """El estado actual no permite la acción (409)."""

    code = "conflict"


class UnauthorizedError(DomainError):
    """Falta sesión o no es válida (401)."""

    code = "unauthorized"
