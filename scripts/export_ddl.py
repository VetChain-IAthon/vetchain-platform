"""Genera docs/schema.postgres.sql con el DDL de PostgreSQL de todas las tablas del ORM.

Uso: python -m scripts.export_ddl
"""
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

import app.db_models  # noqa: F401  (registra todas las tablas)
from app.core.database import Base

OUTPUT = Path("docs/schema.postgres.sql")


def build_ddl() -> str:
    dialect = postgresql.dialect()
    parts = ["-- Generado por python -m scripts.export_ddl. No editar a mano.\n"]
    for table in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";\n")
        for index in sorted(table.indexes, key=lambda index: index.name):
            parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";\n")
    return "\n".join(parts)


def main() -> None:
    OUTPUT.write_text(build_ddl(), encoding="utf-8")
    print(f"DDL escrito en {OUTPUT}")


if __name__ == "__main__":
    main()
