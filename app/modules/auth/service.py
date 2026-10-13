from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import ROLES
from app.core.security import hash_password, verify_password
from app.modules.auth.models import User


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def create_user(db: Session, email: str, password: str, role: str, sales_rep_code: str | None = None) -> User:
    if role not in ROLES:
        raise ValueError(f"Rol no válido: {role}")
    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role=role,
        sales_rep_code=sales_rep_code,
    )
    db.add(user)
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if user and user.active and verify_password(password, user.password_hash):
        return user
    return None
