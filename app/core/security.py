import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, h_hex = stored.split("$")
    except ValueError:
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), _ITERATIONS)
    return hmac.compare_digest(h.hex(), h_hex)


def create_token(user_id: int, role: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": expires}, settings.jwt_secret, algorithm="HS256")


def read_token(token: str) -> dict:
    """Lanza jwt.PyJWTError si el token es inválido o venció."""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
