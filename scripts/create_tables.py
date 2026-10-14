"""Crea todas las tablas con create_all. SOLO para pruebas y prototipos en SQLite.

En PostgreSQL (local, Neon) se usan las migraciones: `alembic upgrade head`.
"""
from app.core.database import Base, engine
import app.db_models  # noqa: F401  (registra todas las tablas)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas:", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    main()
