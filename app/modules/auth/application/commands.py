from dataclasses import dataclass

from app.core.application import Paging


@dataclass(frozen=True)
class CreateSessionCommand:
    email: str
    password: str


@dataclass(frozen=True)
class UpdateOwnProfileCommand:
    user_id: int
    email: str | None = None
    phone: str | None = None
    phone_set: bool = False  # True si la petición trae phone (aunque sea null, para borrarlo)


@dataclass(frozen=True)
class ListUsersQuery:
    paging: Paging


@dataclass(frozen=True)
class CreateUserCommand:
    email: str
    full_name: str
    role: str
    password: str
    phone: str | None = None
    salesperson_code: str | None = None


@dataclass(frozen=True)
class UpdateUserCommand:
    user_id: int
    by_user_id: int
    role: str | None = None
    salesperson_code: str | None = None
    active: bool | None = None
