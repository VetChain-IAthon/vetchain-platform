from app.modules.data_imports.domain.entities import RowError
from app.modules.data_imports.domain.sources import CsvSchema, Record


class CsvRowValidator:
    """Valida una fila del CSV contra su esquema. Devuelve el registro o el error de esa línea."""

    def __init__(self, schema: CsvSchema) -> None:
        self._schema = schema

    def validate(self, line: int, values: list[str]) -> tuple[Record | None, RowError | None]:
        if len(values) != self._schema.width:
            return None, RowError(line, f"Se esperaban {self._schema.width} columnas y llegaron {len(values)}.")
        record: Record = {}
        problems = []
        for column in self._schema.columns:
            try:
                record[column.name] = column.parse(values[column.index])
            except ValueError as error:
                problems.append(str(error))
        if problems:
            return None, RowError(line, "; ".join(problems) + ".")
        return record, None
