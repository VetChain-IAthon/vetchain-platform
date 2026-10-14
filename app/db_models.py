"""Importa todas las tablas para que SQLAlchemy y Alembic las conozcan."""
from app.infrastructure.db import source_models  # noqa: F401
from app.modules.auth.infrastructure import orm as _auth  # noqa: F401
from app.modules.customers.infrastructure import orm as _customers  # noqa: F401
from app.modules.settings.infrastructure import orm as _settings  # noqa: F401
