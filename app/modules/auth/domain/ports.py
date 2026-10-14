from typing import Protocol

from app.core.application import Page, Paging
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.value_objects import CurrentUser, Email


class UserRepository(Protocol):
    def get(self, user_id: int) -> User | None: ...

    def get_by_email(self, email: Email) -> User | None: ...

    def list(self, paging: Paging) -> Page[User]: ...

    def add(self, user: User) -> User:
        """Guarda un usuario nuevo y lo devuelve con id. ConflictError si el correo ya existe."""
        ...

    def save(self, user: User) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    def issue(self, user: CurrentUser) -> str: ...

    def read(self, token: str) -> CurrentUser:
        """UnauthorizedError si el token no es válido o venció."""
        ...
