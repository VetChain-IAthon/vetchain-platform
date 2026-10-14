"""OAuth de Gmail por usuario. Los tokens se cifran antes de guardarse."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.domain import BusinessRuleError
from app.modules.messaging.domain.entities import DeliveryStatus, OutgoingEmail
from app.modules.messaging.infrastructure.orm import GmailConnectionRow, GmailOAuthAttemptRow

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCOPES = "openid email https://www.googleapis.com/auth/gmail.send"


def configured() -> bool:
    return bool(settings.google_oauth_client_id and settings.google_oauth_client_secret and settings.google_oauth_token_key)


def _cipher():
    if not configured():
        raise BusinessRuleError("La conexión con Google aún no está disponible.", "gmail_oauth_not_configured")
    return Fernet(settings.google_oauth_token_key.encode())


def connection(db: Session, user_id: int) -> GmailConnectionRow | None:
    return db.get(GmailConnectionRow, user_id)


def start(db: Session, user_id: int, return_path: str) -> str:
    if not configured():
        raise BusinessRuleError("La conexión con Google aún no está disponible.", "gmail_oauth_not_configured")
    if not return_path.startswith("/") or return_path.startswith("//") or len(return_path) > 500:
        return_path = "/reportes"
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.add(GmailOAuthAttemptRow(state_hash=hashlib.sha256(state.encode()).hexdigest(), user_id=user_id,
                                code_verifier=verifier, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                                return_path=return_path))
    db.commit()
    query = urlencode({"client_id": settings.google_oauth_client_id, "redirect_uri": settings.google_oauth_redirect_uri,
                       "response_type": "code", "scope": SCOPES, "access_type": "offline", "prompt": "select_account consent",
                       "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    return f"{AUTH_URL}?{query}"


def finish(db: Session, state: str, code: str) -> str:
    attempt = db.get(GmailOAuthAttemptRow, hashlib.sha256(state.encode()).hexdigest())
    if attempt is None or attempt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise BusinessRuleError("La conexión caducó. Vuelve a intentarlo.", "gmail_oauth_expired")
    user_id, verifier, return_path = attempt.user_id, attempt.code_verifier, attempt.return_path
    db.delete(attempt)
    db.commit()  # el estado es de un solo uso, incluso si falla Google
    try:
        with httpx.Client(timeout=20) as client:
            token_response = client.post(TOKEN_URL, data={"client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret, "code": code,
                "code_verifier": verifier, "grant_type": "authorization_code",
                "redirect_uri": settings.google_oauth_redirect_uri})
            token_response.raise_for_status()
            tokens = token_response.json()
            identity_response = client.get(USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
            identity_response.raise_for_status()
            identity = identity_response.json()
    except (httpx.HTTPError, KeyError, ValueError):
        raise BusinessRuleError("Google no completó la conexión. Vuelve a intentarlo.", "gmail_oauth_failed") from None
    email = str(identity.get("email", "")).strip().lower()
    if not identity.get("email_verified") or not email.endswith(("@gmail.com", "@googlemail.com")):
        raise BusinessRuleError("Selecciona una cuenta Gmail verificada.", "gmail_account_required")
    refresh = tokens.get("refresh_token")
    existing = connection(db, user_id)
    if not refresh and existing and existing.email == email:
        encrypted = existing.encrypted_refresh_token
    elif refresh:
        encrypted = _cipher().encrypt(refresh.encode()).decode()
    else:
        raise BusinessRuleError("Google no autorizó el envío permanente. Vuelve a conectar la cuenta.", "gmail_refresh_missing")
    if existing:
        existing.email, existing.encrypted_refresh_token = email, encrypted
    else:
        db.add(GmailConnectionRow(user_id=user_id, email=email, encrypted_refresh_token=encrypted))
    db.commit()
    return return_path


def disconnect(db: Session, user_id: int) -> None:
    existing = connection(db, user_id)
    if existing:
        try:
            refresh = _cipher().decrypt(existing.encrypted_refresh_token.encode()).decode()
            with httpx.Client(timeout=10) as client:
                client.post("https://oauth2.googleapis.com/revoke", data={"token": refresh})
        except (httpx.HTTPError, ValueError, InvalidToken, BusinessRuleError):
            pass  # borrar la conexión local sigue siendo seguro aunque Google no responda
        db.delete(existing)
        db.commit()


def send(db: Session, user_id: int, email: OutgoingEmail) -> tuple[DeliveryStatus, str | None]:
    saved = connection(db, user_id)
    if saved is None or email.from_email != saved.email:
        raise BusinessRuleError("Conecta tu cuenta Gmail antes de enviar.", "gmail_connection_required")
    try:
        refresh = _cipher().decrypt(saved.encrypted_refresh_token.encode()).decode()
        with httpx.Client(timeout=30) as client:
            token_response = client.post(TOKEN_URL, data={"client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret, "refresh_token": refresh,
                "grant_type": "refresh_token"})
            if token_response.status_code != 200:
                raise BusinessRuleError("Vuelve a conectar tu Gmail para enviar.", "gmail_reconnect_required")
            access_token = token_response.json()["access_token"]
            message = EmailMessage()
            message["From"] = formataddr((email.from_name, saved.email))
            message["To"] = ", ".join(email.to)
            message["Subject"] = email.subject
            if email.reply_to:
                message["Reply-To"] = email.reply_to
            message.set_content(email.body)
            for attachment in email.attachments:
                main_type, _, sub_type = attachment.content_type.partition("/")
                message.add_attachment(attachment.content, maintype=main_type or "application",
                                       subtype=sub_type or "octet-stream", filename=attachment.file_name)
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
            response = client.post(SEND_URL, json={"raw": raw}, headers={"Authorization": f"Bearer {access_token}"})
            if response.status_code != 200:
                raise BusinessRuleError("Gmail no aceptó el correo. Revisa los destinatarios o vuelve a conectar tu cuenta.", "gmail_send_failed")
            return DeliveryStatus.SENT, response.json().get("id")
    except InvalidToken:
        raise BusinessRuleError("Vuelve a conectar tu Gmail para enviar.", "gmail_reconnect_required") from None
    except (httpx.HTTPError, KeyError, ValueError):
        raise BusinessRuleError("No se pudo conectar con Gmail. Intenta de nuevo.", "gmail_unavailable") from None


class GmailOAuthGateway:
    def __init__(self, db: Session) -> None:
        self.db = db

    def address(self, user_id: int) -> str:
        saved = connection(self.db, user_id)
        if saved is None:
            raise BusinessRuleError("Conecta tu Gmail antes de enviar.", "gmail_connection_required")
        return saved.email

    def name(self, user_id: int) -> str:
        return "Mederi Pharma"

    def send(self, user_id: int, email: OutgoingEmail) -> tuple[DeliveryStatus, str | None]:
        return send(self.db, user_id, email)
