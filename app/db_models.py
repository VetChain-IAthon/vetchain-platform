"""Importa todas las tablas para que SQLAlchemy y Alembic las conozcan."""
from app.infrastructure.db import source_models  # noqa: F401
from app.modules.auth.infrastructure import orm as _auth  # noqa: F401
from app.modules.customers.infrastructure import orm as _customers  # noqa: F401
from app.modules.settings.infrastructure import orm as _settings  # noqa: F401
from app.modules.quotations.infrastructure import orm as _quotations  # noqa: F401
from app.modules.data_imports.infrastructure import orm as _data_imports  # noqa: F401
from app.modules.messaging.infrastructure import orm as _messaging  # noqa: F401
from app.modules.import_planning.infrastructure import orm as _import_planning  # noqa: F401
from app.modules.simulations.infrastructure import orm as _simulations  # noqa: F401
