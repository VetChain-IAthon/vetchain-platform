import pytest

from app.core.application import Paging
from app.core.domain import BusinessRuleError, ConflictError, NotFoundError, UnauthorizedError
from app.modules.auth.application.commands import (
    CreateSessionCommand,
    CreateUserCommand,
    ListUsersQuery,
    UpdateOwnProfileCommand,
    UpdateUserCommand,
)
from app.modules.auth.application.use_cases import (
    AuthenticateToken,
    CreateSession,
    CreateUser,
    ListUsers,
    UpdateOwnProfile,
    UpdateUser,
)
from tests.application.fakes import FakeHasher, FakeSalespeople, FakeTokens, FakeUnitOfWork, InMemoryUserRepository


@pytest.fixture()
def env():
    users, uow = InMemoryUserRepository(), FakeUnitOfWork()
    create = CreateUser(users, FakeHasher(), FakeSalespeople({"002"}), uow)
    manager = create.execute(CreateUserCommand("Gerencia@Mederi.pe", "Ana Gerente", "manager", "clave-segura"))
    seller = create.execute(CreateUserCommand("vende@mederi.pe", "Luis Vende", "salesperson", "clave-segura", None, "002"))
    return users, uow, manager, seller


def test_create_user_rules(env):
    users, uow, _, _ = env
    create = CreateUser(users, FakeHasher(), FakeSalespeople({"002"}), uow)
    with pytest.raises(ConflictError):
        create.execute(CreateUserCommand("gerencia@mederi.pe", "Otra", "manager", "clave-segura"))
    with pytest.raises(BusinessRuleError, match="8 caracteres"):
        create.execute(CreateUserCommand("x@mederi.pe", "X", "manager", "corta"))
    with pytest.raises(BusinessRuleError, match="Rol no válido"):
        create.execute(CreateUserCommand("x@mederi.pe", "X", "admin", "clave-segura"))
    with pytest.raises(BusinessRuleError, match="código de vendedor"):
        create.execute(CreateUserCommand("x@mederi.pe", "X", "salesperson", "clave-segura"))
    with pytest.raises(BusinessRuleError, match="No existe el vendedor 999"):
        create.execute(CreateUserCommand("x@mederi.pe", "X", "salesperson", "clave-segura", None, "999"))
    assert uow.commits == 2  # solo los dos del fixture


def test_create_session(env):
    users, uow, manager, _ = env
    login = CreateSession(users, FakeHasher(), FakeTokens(), uow)
    result = login.execute(CreateSessionCommand(" GERENCIA@mederi.pe ", "clave-segura"))
    assert result.access_token == f"token:{manager.id}"
    for email, password in [("gerencia@mederi.pe", "otra"), ("nadie@mederi.pe", "clave-segura"), ("no-es-correo", "x")]:
        with pytest.raises(UnauthorizedError, match="Correo o contraseña incorrectos"):
            login.execute(CreateSessionCommand(email, password))


def test_inactive_user_cannot_log_in_nor_use_token(env):
    users, uow, manager, seller = env
    UpdateUser(users, FakeSalespeople({"002"}), uow).execute(UpdateUserCommand(seller.id, manager.id, active=False))
    with pytest.raises(UnauthorizedError):
        CreateSession(users, FakeHasher(), FakeTokens(), uow).execute(CreateSessionCommand("vende@mederi.pe", "clave-segura"))
    with pytest.raises(UnauthorizedError):
        AuthenticateToken(FakeTokens(), users, uow).execute(f"token:{seller.id}")
    assert AuthenticateToken(FakeTokens(), users, uow).execute(f"token:{manager.id}").role == "manager"


def test_update_own_profile(env):
    users, uow, manager, seller = env
    update = UpdateOwnProfile(users, uow)
    user = update.execute(UpdateOwnProfileCommand(seller.id, phone="987654321", phone_set=True))
    assert user.phone == "987654321" and user.email.value == "vende@mederi.pe"
    user = update.execute(UpdateOwnProfileCommand(seller.id, email="nuevo@mederi.pe"))
    assert user.phone == "987654321"  # phone no vino: no se toca
    with pytest.raises(ConflictError):
        update.execute(UpdateOwnProfileCommand(seller.id, email="gerencia@mederi.pe"))
    assert update.execute(UpdateOwnProfileCommand(seller.id, phone=None, phone_set=True)).phone is None


def test_update_user_role_and_activation(env):
    users, uow, manager, seller = env
    update = UpdateUser(users, FakeSalespeople({"002", "003"}), uow)
    assert update.execute(UpdateUserCommand(seller.id, manager.id, salesperson_code="003")).salesperson_code == "003"
    promoted = update.execute(UpdateUserCommand(seller.id, manager.id, role="manager"))
    assert promoted.role.value == "manager" and promoted.salesperson_code is None
    with pytest.raises(BusinessRuleError):
        update.execute(UpdateUserCommand(seller.id, manager.id, role="salesperson"))  # falta código
    with pytest.raises(ConflictError):
        update.execute(UpdateUserCommand(manager.id, manager.id, active=False))
    with pytest.raises(NotFoundError):
        update.execute(UpdateUserCommand(99, manager.id, active=True))


def test_list_users_paginates(env):
    users, uow, _, _ = env
    page = ListUsers(users, uow).execute(ListUsersQuery(Paging(page=2, per_page=1)))
    assert page.total == 2 and [u.email.value for u in page.items] == ["vende@mederi.pe"]
