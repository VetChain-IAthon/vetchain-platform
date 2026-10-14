import pytest


@pytest.fixture(autouse=True)
def clean_db():
    """Las pruebas de aplicación usan puertos falsos: no tocan la base de datos."""
    yield
