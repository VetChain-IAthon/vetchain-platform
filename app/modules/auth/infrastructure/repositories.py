from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.application import Page, Paging
from app.core.domain import ConflictError
from app.infrastructure.db.source_models import Salesperson
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.value_objects import Email, Role
from app.modules.auth.infrastructure.orm import UserRow


def _to_entity(row: UserRow) -> User:
    return User(
        id=row.id,
        email=Email(row.email),
        full_name=row.full_name,
        role=Role(row.role),
        password_hash=row.password_hash,
        phone=row.phone,
        salesperson_code=row.salesperson_code,
        active=row.active,
    )


def _copy_to_row(user: User, row: UserRow) -> None:
    row.email = user.email.value
    row.full_name = user.full_name
    row.role = user.role.value
    row.password_hash = user.password_hash
    row.phone = user.phone
    row.salesperson_code = user.salesperson_code
    row.active = user.active


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        row = self._session.get(UserRow, user_id)
        return None if row is None else _to_entity(row)

    def get_by_email(self, email: Email) -> User | None:
        row = self._session.scalar(select(UserRow).where(UserRow.email == email.value))
        return None if row is None else _to_entity(row)

    def list(self, paging: Paging) -> Page[User]:
        total = self._session.scalar(select(func.count()).select_from(UserRow))
        rows = self._session.scalars(select(UserRow).order_by(UserRow.id).offset(paging.offset).limit(paging.per_page))
        return Page.of([_to_entity(row) for row in rows], total, paging)

    def add(self, user: User) -> User:
        row = UserRow()
        _copy_to_row(user, row)
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            raise ConflictError("Ya existe un usuario con ese correo.", "email_taken") from None
        user.id = row.id
        return user

    def save(self, user: User) -> None:
        row = self._session.get(UserRow, user.id)
        _copy_to_row(user, row)
        self._session.flush()


class SqlSalespersonDirectory:
    def __init__(self, session: Session) -> None:
        self._session = session

    def exists(self, code: str) -> bool:
        return self._session.get(Salesperson, code) is not None
