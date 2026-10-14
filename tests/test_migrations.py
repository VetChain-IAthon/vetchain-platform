"""La migración de Alembic crea exactamente lo que define el ORM (en la base de pruebas, SQLite)."""
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.database import Base, engine


def test_upgrade_matches_orm_and_downgrade_cleans():
    config = Config("alembic.ini")
    Base.metadata.drop_all(engine)
    command.upgrade(config, "head")
    command.check(config)  # falla si el ORM tiene cambios sin migración
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables) | {"alembic_version"}
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
