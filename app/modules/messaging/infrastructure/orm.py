from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailSenderRow(Base):
    __tablename__ = "email_senders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(200), unique=True)  # ventas@mederi.pe o @mederi.pe
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class EmailLogRow(Base):
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    from_email: Mapped[str] = mapped_column(String(200))
    recipients: Mapped[str] = mapped_column(Text)  # separados por coma
    subject: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20))
    attachment_names: Mapped[str] = mapped_column(Text, default="")
    provider_message_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GmailConnectionRow(Base):
    __tablename__ = "gmail_connections"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email: Mapped[str] = mapped_column(String(200))
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)


class GmailOAuthAttemptRow(Base):
    __tablename__ = "gmail_oauth_attempts"

    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    code_verifier: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    return_path: Mapped[str] = mapped_column(String(500))
