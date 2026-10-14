from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./vetchain.db"
    jwt_secret: str = "cambia-esto-por-un-valor-largo-y-aleatorio"
    jwt_expire_minutes: int = 480
    gemini_api_key: str = ""
    resend_api_key: str = ""  # sin clave, los correos se simulan (se registran pero no salen)
    gmail_smtp_email: str = ""  # cuenta Gmail que enviará los mensajes
    gmail_smtp_app_password: str = ""  # contraseña de aplicación de Google, no la contraseña de inicio de sesión
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/gmail/callback"
    google_oauth_token_key: str = ""  # clave Fernet para cifrar tokens de actualización
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    model_path: str = "models/model.json"

    # Seed de usuarios (scripts/seed_users.py). Vacíos por defecto.
    seed_manager_email: str = ""
    seed_manager_password: str = ""
    seed_manager_name: str = ""
    seed_manager_phone: str = ""
    seed_salesperson_email: str = ""
    seed_salesperson_password: str = ""
    seed_salesperson_name: str = ""
    seed_salesperson_phone: str = ""
    seed_salesperson_code: str = ""

    @property
    def database_url_sqlalchemy(self) -> str:
        """Neon y Render entregan postgres:// o postgresql://; SQLAlchemy con psycopg 3 pide postgresql+psycopg://."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
