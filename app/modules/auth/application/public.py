"""Fachada de auth para otros módulos y para app/core/auth.py. Solo tipos simples.

La interfaz de auth registra aquí, al cargarse, la función que arma y ejecuta AuthenticateToken (`configure`).
Así esta capa no conoce la infraestructura.
"""
from collections.abc import Callable

from app.core.application import SessionUser

_authenticator: Callable[[str], SessionUser] | None = None


def configure(authenticator: Callable[[str], SessionUser]) -> None:
    global _authenticator
    _authenticator = authenticator


def authenticate_token(token: str) -> SessionUser:
    """UnauthorizedError si el token no es válido, venció o el usuario está inactivo."""
    if _authenticator is None:
        raise RuntimeError("auth no está configurado: falta importar app.modules.auth.interface.")
    return _authenticator(token)
