import pytest


@pytest.fixture(autouse=True)
def clean_db():
    """Las pruebas de dominio son puras: no tocan la base de datos."""
    yield
