import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from app.core.domain import UnauthorizedError
from app.modules.auth.domain.value_objects import CurrentUser, Role

_ITERATIONS = 200_000


class Pbkdf2PasswordHasher:
    def hash(self, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
        return f"{salt.hex()}${digest.hex()}"

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            salt_hex, digest_hex = password_hash.split("$")
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), _ITERATIONS)
        return hmac.compare_digest(digest.hex(), digest_hex)


class JwtTokenService:
    def __init__(self, secret: str, expire_minutes: int) -> None:
        self._secret = secret
        self._expire = timedelta(minutes=expire_minutes)

    def issue(self, user: CurrentUser) -> str:
        expires = datetime.now(timezone.utc) + self._expire
        claims = {"sub": str(user.id), "role": user.role.value, "spc": user.salesperson_code, "exp": expires}
        return jwt.encode(claims, self._secret, algorithm="HS256")

    def read(self, token: str) -> CurrentUser:
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"])
            return CurrentUser(int(claims["sub"]), Role(claims["role"]), claims.get("spc"))
        except (jwt.PyJWTError, KeyError, ValueError):
            raise UnauthorizedError("La sesión no es válida o venció.", "invalid_session") from None
