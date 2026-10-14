"""Puertos falsos en memoria para probar los casos de uso sin base de datos ni red."""
from dataclasses import replace

from app.core.application import Page, Paging
from app.core.domain import UnauthorizedError
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.value_objects import CurrentUser, Email


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.rollbacks += 1

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}

    def get(self, user_id: int) -> User | None:
        user = self.users.get(user_id)
        return None if user is None else replace(user)

    def get_by_email(self, email: Email) -> User | None:
        return next((replace(u) for u in self.users.values() if u.email == email), None)

    def list(self, paging: Paging) -> Page[User]:
        users = sorted(self.users.values(), key=lambda u: u.id)
        return Page.of(users[paging.offset:paging.offset + paging.per_page], len(users), paging)

    def add(self, user: User) -> User:
        user.id = len(self.users) + 1
        self.users[user.id] = replace(user)
        return user

    def save(self, user: User) -> None:
        self.users[user.id] = replace(user)


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeTokens:
    def issue(self, user: CurrentUser) -> str:
        return f"token:{user.id}"

    def read(self, token: str) -> CurrentUser:
        from app.modules.auth.domain.value_objects import Role

        if not token.startswith("token:"):
            raise UnauthorizedError("La sesión no es válida o venció.", "invalid_session")
        return CurrentUser(int(token.split(":")[1]), Role.MANAGER, None)


class FakeSalespeople:
    def __init__(self, codes: set[str]) -> None:
        self.codes = codes

    def exists(self, code: str) -> bool:
        return code in self.codes


class InMemorySettingsRepository:
    def __init__(self) -> None:
        self.pricing = None
        self.rules = {}
        self.thresholds = None

    def get_pricing(self):
        return self.pricing

    def save_pricing(self, pricing) -> None:
        self.pricing = pricing

    def list_level_rules(self):
        return list(self.rules.values())

    def save_level_rule(self, rule) -> None:
        self.rules[rule.level] = rule

    def get_thresholds(self):
        return self.thresholds

    def save_thresholds(self, thresholds) -> None:
        self.thresholds = thresholds
