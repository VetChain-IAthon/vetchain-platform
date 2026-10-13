"""Importa todas las tablas para que SQLAlchemy las conozca (usado al crear tablas y en pruebas)."""
from app.core import mederi_tables  # noqa: F401
from app.modules.auth import models as _auth  # noqa: F401
from app.modules.customers import models as _customers  # noqa: F401
from app.modules.pricing import models as _pricing  # noqa: F401
from app.modules.quotes import models as _quotes  # noqa: F401
