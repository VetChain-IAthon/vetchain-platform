"""Dependencias de sesión compartidas por las interfaces de todos los módulos.

current_user verifica el JWT (Authorization: Bearer) a través de la fachada pública de auth.
require_role limita por rol. forced_salesperson_code aplica el alcance del vendedor sin confiar en la web.
"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.application import SessionUser
from app.core.domain import ForbiddenError, UnauthorizedError

_bearer = HTTPBearer(auto_error=False, description="Token de POST /api/v1/sessions")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> SessionUser:
    from app.modules.auth.application import public as auth_public  # import tardío: auth también usa core

    if credentials is None:
        raise UnauthorizedError("Falta iniciar sesión.", "missing_session")
    return auth_public.authenticate_token(credentials.credentials)


def require_role(*roles: str):
    """Uso: user: SessionUser = Depends(require_role(MANAGER))."""

    def _dependency(user: SessionUser = Depends(current_user)) -> SessionUser:
        if user.role not in roles:
            raise ForbiddenError("Tu rol no tiene acceso a esto.", "role_not_allowed")
        return user

    return _dependency


def forced_salesperson_code(user: SessionUser, requested: str | None) -> str | None:
    """Gerencia filtra por el vendedor que pida (o ninguno); un vendedor siempre ve solo su cartera."""
    return requested if user.is_manager else user.salesperson_code
