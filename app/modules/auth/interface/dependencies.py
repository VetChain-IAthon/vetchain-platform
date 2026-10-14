"""Cableado de auth: crea los adaptadores y arma los casos de uso. Único lugar de la interfaz que ve la infraestructura."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.application import SessionUser
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.auth.application import public
from app.modules.auth.application.use_cases import (
    AuthenticateToken,
    CreateSession,
    CreateUser,
    GetCurrentUser,
    ListUsers,
    UpdateOwnProfile,
    UpdateUser,
)
from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository, SqlSalespersonDirectory
from app.modules.auth.infrastructure.security import JwtTokenService, Pbkdf2PasswordHasher


def _token_service() -> JwtTokenService:
    return JwtTokenService(settings.jwt_secret, settings.jwt_expire_minutes)


def _uow(db: Session) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session=db)


def get_create_session(db: Session = Depends(get_db)) -> CreateSession:
    return CreateSession(SqlAlchemyUserRepository(db), Pbkdf2PasswordHasher(), _token_service(), _uow(db))


def get_current_user_use_case(db: Session = Depends(get_db)) -> GetCurrentUser:
    return GetCurrentUser(SqlAlchemyUserRepository(db), _uow(db))


def get_update_own_profile(db: Session = Depends(get_db)) -> UpdateOwnProfile:
    return UpdateOwnProfile(SqlAlchemyUserRepository(db), _uow(db))


def get_list_users(db: Session = Depends(get_db)) -> ListUsers:
    return ListUsers(SqlAlchemyUserRepository(db), _uow(db))


def get_create_user(db: Session = Depends(get_db)) -> CreateUser:
    return CreateUser(SqlAlchemyUserRepository(db), Pbkdf2PasswordHasher(), SqlSalespersonDirectory(db), _uow(db))


def get_update_user(db: Session = Depends(get_db)) -> UpdateUser:
    return UpdateUser(SqlAlchemyUserRepository(db), SqlSalespersonDirectory(db), _uow(db))


def build_create_user(db: Session) -> CreateUser:
    """Para scripts (seed de usuarios)."""
    return get_create_user(db)


def authenticate(token: str) -> SessionUser:
    with SessionLocal() as db:
        return AuthenticateToken(_token_service(), SqlAlchemyUserRepository(db), _uow(db)).execute(token)


def user_names(user_ids: list[int]) -> dict[int, str]:
    with SessionLocal() as db:
        repository = SqlAlchemyUserRepository(db)
        users = [repository.get(user_id) for user_id in user_ids]
    return {user.id: user.full_name for user in users if user is not None}


public.configure(authenticate, user_names)
