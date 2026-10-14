from fastapi import APIRouter, Depends, Query

from app.core.application import MANAGER, Paging, SessionUser
from app.core.auth import current_user, require_role
from app.modules.auth.application.commands import (
    CreateSessionCommand,
    CreateUserCommand,
    ListUsersQuery,
    UpdateOwnProfileCommand,
    UpdateUserCommand,
)
from app.modules.auth.application.use_cases import (
    CreateSession,
    CreateUser,
    GetCurrentUser,
    ListUsers,
    UpdateOwnProfile,
    UpdateUser,
)
from app.modules.auth.interface import dependencies as deps
from app.modules.auth.interface.schemas import (
    MeUpdateIn,
    SessionCreateIn,
    SessionOut,
    UserCreateIn,
    UserOut,
    UserPageOut,
    UserUpdateIn,
)

router = APIRouter()
manager_only = require_role(MANAGER)


@router.post("/sessions", response_model=SessionOut, status_code=201, tags=["sesión y perfil"])
def create_session(body: SessionCreateIn, use_case: CreateSession = Depends(deps.get_create_session)):
    """Inicia sesión y devuelve el token (JWT) para `Authorization: Bearer`."""
    result = use_case.execute(CreateSessionCommand(body.email, body.password))
    return SessionOut(access_token=result.access_token, user=UserOut.from_domain(result.user))


@router.get("/me", response_model=UserOut, tags=["sesión y perfil"])
def get_me(
    user: SessionUser = Depends(current_user),
    use_case: GetCurrentUser = Depends(deps.get_current_user_use_case),
):
    """Usuario actual y su rol (la web arma el menú con esto)."""
    return UserOut.from_domain(use_case.execute(user.id))


@router.patch("/me", response_model=UserOut, tags=["sesión y perfil"])
def update_me(
    body: MeUpdateIn,
    user: SessionUser = Depends(current_user),
    use_case: UpdateOwnProfile = Depends(deps.get_update_own_profile),
):
    """Cambia el correo o el teléfono propios."""
    command = UpdateOwnProfileCommand(user.id, body.email, body.phone, phone_set="phone" in body.model_fields_set)
    return UserOut.from_domain(use_case.execute(command))


@router.get("/users", response_model=UserPageOut, tags=["usuarios"])
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: SessionUser = Depends(manager_only),
    use_case: ListUsers = Depends(deps.get_list_users),
):
    result = use_case.execute(ListUsersQuery(Paging(page, per_page)))
    return UserPageOut(
        items=[UserOut.from_domain(u) for u in result.items], total=result.total, page=result.page, per_page=result.per_page
    )


@router.post("/users", response_model=UserOut, status_code=201, tags=["usuarios"])
def create_user(
    body: UserCreateIn,
    _: SessionUser = Depends(manager_only),
    use_case: CreateUser = Depends(deps.get_create_user),
):
    command = CreateUserCommand(body.email, body.full_name, body.role, body.password, body.phone, body.salesperson_code)
    return UserOut.from_domain(use_case.execute(command))


@router.patch("/users/{user_id}", response_model=UserOut, tags=["usuarios"])
def update_user(
    user_id: int,
    body: UserUpdateIn,
    manager: SessionUser = Depends(manager_only),
    use_case: UpdateUser = Depends(deps.get_update_user),
):
    """Cambia el rol (y el código de vendedor) o activa / desactiva la cuenta."""
    command = UpdateUserCommand(user_id, manager.id, body.role, body.salesperson_code, body.active)
    return UserOut.from_domain(use_case.execute(command))
