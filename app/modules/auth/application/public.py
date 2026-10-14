"""Fachada de auth para otros módulos y para app/core/auth.py. Solo tipos simples.

La interfaz de auth registra aquí, al cargarse, la función que arma y ejecuta AuthenticateToken (`configure`).
Así esta capa no conoce la infraestructura.
"""
from collections.abc import Callable

from app.core.application import SessionUser

_authenticator: Callable[[str], SessionUser] | None = None
_name_lookup: Callable[[list[int]], dict[int, str]] | None = None


def configure(authenticator: Callable[[str], SessionUser],
              name_lookup: Callable[[list[int]], dict[int, str]] | None = None) -> None:
    global _authenticator, _name_lookup
    _authenticator, _name_lookup = authenticator, name_lookup


def authenticate_token(token: str) -> SessionUser:
    """UnauthorizedError si el token no es válido, venció o el usuario está inactivo."""
    if _authenticator is None:
        raise RuntimeError("auth no está configurado: falta importar app.modules.auth.interface.")
    return _authenticator(token)


def user_names(user_ids: list[int]) -> dict[int, str]:
    """Nombre completo de cada usuario que exista (por ejemplo, para mostrar quién descartó a un cliente)."""
    if _name_lookup is None:
        raise RuntimeError("auth no está configurado: falta importar app.modules.auth.interface.")
    return _name_lookup(user_ids)
