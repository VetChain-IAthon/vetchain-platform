import os

os.environ["DATABASE_URL"] = "sqlite:///./test_vetchain.db"
os.environ["JWT_SECRET"] = "secreto-solo-para-pruebas-con-largo-suficiente-123"

import pytest
from fastapi.testclient import TestClient

import app.db_models  # noqa: F401
from app.core.database import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


PASSWORD = "clave-segura-1"


@pytest.fixture()
def login(client, db):
    """Crea un usuario (y el vendedor 002 de Defontana) y devuelve la cabecera Authorization de su sesión."""
    from app.infrastructure.db.source_models import Salesperson
    from app.modules.auth.application.commands import CreateUserCommand
    from app.modules.auth.interface.dependencies import build_create_user

    db.add(Salesperson(code="002", name="ANA RIOS", location=None, is_active=True))
    db.commit()

    def _login(role: str = "manager", email: str | None = None, salesperson_code: str | None = None) -> dict:
        email = email or f"{role}@mederi.pe"
        if role == "salesperson":
            salesperson_code = salesperson_code or "002"
        build_create_user(db).execute(CreateUserCommand(email, f"Usuario {role}", role, PASSWORD, None, salesperson_code))
        response = client.post("/api/v1/sessions", json={"email": email, "password": PASSWORD})
        assert response.status_code == 201, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _login
