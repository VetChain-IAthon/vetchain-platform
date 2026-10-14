"""Casos de uso de auth. Coordinan puertos y dominio; las reglas viven en el dominio."""
from dataclasses import dataclass

from app.core.application import Page, SessionUser
from app.core.domain import BusinessRuleError, NotFoundError, UnauthorizedError, UnitOfWork
from app.modules.auth.application.commands import (
    CreateSessionCommand,
    CreateUserCommand,
    ListUsersQuery,
    UpdateOwnProfileCommand,
    UpdateUserCommand,
)
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.ports import PasswordHasher, SalespersonDirectory, TokenService, UserRepository
from app.modules.auth.domain.services import PasswordPolicy, UserRules
from app.modules.auth.domain.value_objects import CurrentUser, Email, Role

_INVALID_LOGIN = "Correo o contraseña incorrectos."


def _role(value: str) -> Role:
    try:
        return Role(value)
    except ValueError:
        raise BusinessRuleError(f"Rol no válido: {value}. Usa manager o salesperson.", "invalid_role") from None


def _get(users: UserRepository, user_id: int) -> User:
    user = users.get(user_id)
    if user is None:
        raise NotFoundError("El usuario no existe.", "user_not_found")
    return user


@dataclass(frozen=True)
class SessionResult:
    access_token: str
    user: User


class CreateSession:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService, uow: UnitOfWork) -> None:
        self.users, self.hasher, self.tokens, self.uow = users, hasher, tokens, uow

    def execute(self, command: CreateSessionCommand) -> SessionResult:
        with self.uow:
            try:
                email = Email(command.email)
            except BusinessRuleError:
                raise UnauthorizedError(_INVALID_LOGIN, "invalid_credentials") from None
            user = self.users.get_by_email(email)
            if user is None or not self.hasher.verify(command.password, user.password_hash) or not user.can_log_in():
                raise UnauthorizedError(_INVALID_LOGIN, "invalid_credentials")
            return SessionResult(self.tokens.issue(user.to_current_user()), user)


class GetCurrentUser:
    def __init__(self, users: UserRepository, uow: UnitOfWork) -> None:
        self.users, self.uow = users, uow

    def execute(self, user_id: int) -> User:
        with self.uow:
            user = self.users.get(user_id)
            if user is None or not user.can_log_in():
                raise UnauthorizedError("El usuario no existe o está inactivo.", "inactive_user")
            return user


class UpdateOwnProfile:
    def __init__(self, users: UserRepository, uow: UnitOfWork) -> None:
        self.users, self.uow = users, uow

    def execute(self, command: UpdateOwnProfileCommand) -> User:
        with self.uow:
            user = _get(self.users, command.user_id)
            email = Email(command.email) if command.email is not None else user.email
            if email != user.email:
                UserRules.ensure_email_available(self.users.get_by_email(email), user.id)
            user.update_profile(email, command.phone if command.phone_set else user.phone)
            self.users.save(user)
            self.uow.commit()
            return user


class ListUsers:
    def __init__(self, users: UserRepository, uow: UnitOfWork) -> None:
        self.users, self.uow = users, uow

    def execute(self, query: ListUsersQuery) -> Page[User]:
        with self.uow:
            return self.users.list(query.paging)


class CreateUser:
    def __init__(
        self, users: UserRepository, hasher: PasswordHasher, salespeople: SalespersonDirectory, uow: UnitOfWork
    ) -> None:
        self.users, self.hasher, self.salespeople, self.uow = users, hasher, salespeople, uow

    def execute(self, command: CreateUserCommand) -> User:
        with self.uow:
            PasswordPolicy.check(command.password)
            email = Email(command.email)
            UserRules.ensure_email_available(self.users.get_by_email(email))
            code = (command.salesperson_code or "").strip() or None
            UserRules.ensure_salesperson_exists(code, code is not None and self.salespeople.exists(code))
            user = User(
                email=email,
                full_name=command.full_name,
                role=_role(command.role),
                password_hash=self.hasher.hash(command.password),
                phone=command.phone,
                salesperson_code=code,
            )
            user = self.users.add(user)
            self.uow.commit()
            return user


class UpdateUser:
    """Cambiar rol (y código de vendedor) o activar / desactivar. Solo gerencia (lo controla la interfaz)."""

    def __init__(self, users: UserRepository, salespeople: SalespersonDirectory, uow: UnitOfWork) -> None:
        self.users, self.salespeople, self.uow = users, salespeople, uow

    def execute(self, command: UpdateUserCommand) -> User:
        with self.uow:
            user = _get(self.users, command.user_id)
            if command.role is not None or command.salesperson_code is not None:
                role = _role(command.role) if command.role is not None else user.role
                code = (command.salesperson_code or "").strip() or None
                if role is Role.SALESPERSON and code is None:
                    code = user.salesperson_code
                if role is Role.MANAGER and command.salesperson_code is None:
                    code = None
                UserRules.ensure_salesperson_exists(code, code is not None and self.salespeople.exists(code))
                user.change_role(role, code)
            if command.active is False:
                user.deactivate(by=CurrentUser(command.by_user_id, Role.MANAGER, None))
            elif command.active is True:
                user.activate()
            self.users.save(user)
            self.uow.commit()
            return user


class AuthenticateToken:
    """Verifica el token y que el usuario siga activo. Lo usa la fachada pública para todos los módulos."""

    def __init__(self, tokens: TokenService, users: UserRepository, uow: UnitOfWork) -> None:
        self.tokens, self.users, self.uow = tokens, users, uow

    def execute(self, token: str) -> SessionUser:
        claims = self.tokens.read(token)
        user = GetCurrentUser(self.users, self.uow).execute(claims.id)
        return SessionUser(user.id, user.role.value, user.salesperson_code)
