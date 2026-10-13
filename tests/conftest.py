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
