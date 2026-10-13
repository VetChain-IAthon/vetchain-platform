from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./vetchain.db"
    jwt_secret: str = "cambia-esto-por-un-valor-largo-y-aleatorio"
    jwt_expire_minutes: int = 480
    gemini_api_key: str = ""
    cors_origins: str = "http://localhost:3000"
    model_path: str = "models/model.json"

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
