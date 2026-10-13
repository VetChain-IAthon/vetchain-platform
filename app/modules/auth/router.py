from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import current_user
from app.core.security import create_token
from app.modules.auth import service
from app.modules.auth.schemas import LoginIn, TokenOut, UserOut

router = APIRouter()


@router.get("/status")
def status() -> dict:
    return {"module": "auth", "status": "active"}


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = service.authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(http_status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos.")
    return TokenOut(access_token=create_token(user.id, user.role))


@router.get("/me", response_model=UserOut)
def me(user=Depends(current_user)):
    return user


# PENDIENTE: crear, listar y desactivar usuarios (solo rol management).
