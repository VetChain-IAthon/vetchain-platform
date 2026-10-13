from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import read_token

ROLES = ("management", "sales_rep")
_bearer = HTTPBearer(auto_error=False)


def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """Devuelve el usuario de la sesión. Importa auth aquí dentro para no crear un ciclo."""
    from app.modules.auth import service as auth_service

    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta iniciar sesión.")
    try:
        payload = read_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión no es válida o venció.")
    user = auth_service.get_by_id(db, int(payload["sub"]))
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El usuario no existe o está inactivo.")
    return user


def require_role(*roles: str):
    """Uso: Depends(require_role("management"))."""

    def _dep(user=Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu rol no tiene acceso a esto.")
        return user

    return _dep
