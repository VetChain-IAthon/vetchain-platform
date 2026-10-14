"""Cargas desde Ajustes: registro de cada carga, filas en revisión y escritura con el cargador de Defontana."""
from __future__ import annotations  # el método list oculta al tipo list dentro de la clase

import json
import re
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.application import Page, Paging
from app.core.domain import DataOrigin
from app.infrastructure.db.source_models import Order, OrderLine, Product, Receipt, StockBalance
from app.infrastructure.loaders.defontana_csv import load_source, spec_for, validate_source
from app.modules.data_imports.domain.entities import DataImport, ImportStatus, RowError
from app.modules.data_imports.domain.sources import SOURCES, SourceName
from app.modules.data_imports.infrastructure.orm import DataImportRow


def _to_domain(row: DataImportRow) -> DataImport:
    return DataImport(
        source=SourceName(row.source), origin=DataOrigin(row.origin), rows_read=row.rows_read,
        rows_with_error=row.rows_with_error, created_at=row.created_at, status=ImportStatus(row.status),
        decided_at=row.decided_at, errors=tuple(RowError(line, message) for line, message in json.loads(row.errors)),
        id=row.id, file_name=row.file_name, rows_loaded=row.rows_loaded, created_by=row.created_by,
    )


class SqlDataImportRepository:
    """Implementa DataImportRepository y StagingStore sobre la tabla data_imports."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, data_import: DataImport) -> DataImport:
        row = DataImportRow(
            source=data_import.source.value, origin=data_import.origin.value, status=data_import.status.value,
            file_name=data_import.file_name, rows_read=data_import.rows_read, rows_with_error=data_import.rows_with_error,
            rows_loaded=data_import.rows_loaded, errors=json.dumps([[e.line, e.message] for e in data_import.errors]),
            created_by=data_import.created_by, created_at=data_import.created_at, decided_at=data_import.decided_at,
        )
        self._session.add(row)
        self._session.flush()
        return _to_domain(row)

    def get(self, import_id: int) -> DataImport | None:
        row = self._session.get(DataImportRow, import_id)
        return None if row is None else _to_domain(row)

    def list(self, paging: Paging) -> Page[DataImport]:
        total = self._session.scalar(select(func.count()).select_from(DataImportRow))
        rows = self._session.scalars(
            select(DataImportRow).order_by(DataImportRow.created_at.desc(), DataImportRow.id.desc())
            .offset(paging.offset).limit(paging.per_page)
        )
        return Page.of([_to_domain(row) for row in rows], total, paging)

    def save(self, data_import: DataImport) -> None:
        row = self._session.get(DataImportRow, data_import.id)
        row.status, row.decided_at, row.rows_loaded = data_import.status.value, data_import.decided_at, data_import.rows_loaded

    def last_confirmed(self) -> dict[SourceName, DataImport]:
        rows = self._session.scalars(
            select(DataImportRow).where(DataImportRow.status == ImportStatus.CONFIRMED.value)
            .order_by(DataImportRow.decided_at.desc(), DataImportRow.id.desc())
        )
        latest: dict[SourceName, DataImport] = {}
        for row in rows:
            latest.setdefault(SourceName(row.source), _to_domain(row))
        return latest

    # --- StagingStore ---

    def put(self, import_id: int, rows: list[list[str]]) -> None:
        self._session.get(DataImportRow, import_id).staged_rows = json.dumps(rows, ensure_ascii=False)

    def take(self, import_id: int) -> list[list[str]]:
        stored = self._session.get(DataImportRow, import_id).staged_rows
        return json.loads(stored) if stored else []

    def discard(self, import_id: int) -> None:
        self._session.get(DataImportRow, import_id).staged_rows = None


class DefontanaSourceLoader:
    """Implementa SourceLoader con el mismo cargador de la carga inicial (reglas de campos vacíos, FK y upsert)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def validate(self, source: SourceName, rows: list[list[str]]) -> tuple[int, list[RowError]]:
        spec = spec_for(source.value)
        report = validate_source(self._session, spec, rows)
        return report.rows_read, [RowError(line, _friendly(SOURCES[source], spec, rows[line - 1], reason))
                                  for line, reason in report.rejected_lines]

    def existing_lines(self, source: SourceName, rows: list[list[str]]) -> set[int]:
        spec = spec_for(source.value)
        fields = {f.name: f for f in spec.fields}
        keys = [k for k in spec.conflict_keys if k != "dup_seq"]  # detalle: la línea repetida se toma como la primera
        columns = [getattr(spec.model, k) for k in keys]
        existing = {tuple(str(v) for v in key) for key in self._session.execute(select(*columns))}
        found = set()
        for line, row in enumerate(rows, start=1):
            try:
                key = tuple(_normalize(row[fields[k].index].strip(), fields[k].kind) for k in keys)
            except (IndexError, ValueError):
                continue
            if key in existing:
                found.add(line)
        return found

    def load(self, source: SourceName, rows: list[list[str]]) -> int:
        return load_source(self._session, spec_for(source.value), rows).rows_loaded


def _normalize(value: str, kind: str) -> str:
    """Las claves enteras (año, mes, línea) se comparan como número; los códigos de texto, tal cual (001 ≠ 1)."""
    return str(int(value)) if kind == "int" else value


_PARENT_FILES = {"salespeople": "vendedores", "customers": "clientes", "products": "productos", "orders": "pedidos"}
_FORMATS = {"date": "usa el formato AAAA-MM-DD, por ejemplo 2026-04-21", "decimal": "usa punto decimal, por ejemplo 1250.50",
            "int": "debe ser un número entero", "bool": "debe ser 1 (sí) o 0 (no)"}


def _friendly(source, spec, row: list[str], reason: str) -> str:
    """Traduce el motivo del cargador a un mensaje que diga qué pasó y cómo corregirlo, con el valor de la fila."""
    fields = {f.name: f for f in spec.fields}

    def value(name: str) -> str:
        field = fields.get(name)
        return row[field.index].strip() if field and field.index < len(row) else ""

    match = re.fullmatch(r"(\w+) no existe en (\w+)", reason)
    if match:
        column, table = match.groups()
        parent = _PARENT_FILES.get(table, table)
        return (f"{source.header_for(column)} «{value(column)}» no existe en {parent}. "
                f"Carga primero el archivo de {parent} o corrige el código.")
    match = re.fullmatch(r"falta (\w+)", reason)
    if match:
        return f"Falta {source.header_for(match.group(1))}: es obligatorio."
    match = re.fullmatch(r"(\w+) inválido", reason)
    if match:
        name = match.group(1)
        hint = _FORMATS.get(fields[name].kind, "") if name in fields else ""
        return f"Valor no válido en {source.header_for(name)} («{value(name)}»){f': {hint}' if hint else ''}."
    match = re.fullmatch(r"se esperaban (\d+) columnas", reason)
    if match:
        return f"La fila trae {len(row)} columnas y se esperaban {match.group(1)}. Revisa comas de más o celdas combinadas."
    if reason == "clave repetida en el archivo":
        return "Esta fila repite el código de otra fila del mismo archivo. Deja solo una."
    return reason[:1].upper() + reason[1:] + "."


_DATES = {
    SourceName.ORDERS: Order.order_date, SourceName.RECEIPTS: Receipt.receipt_date,
    SourceName.STOCK_BALANCES: StockBalance.period_end,
}


class SqlSourceStats:
    """Filas y período de cada tabla de Defontana."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def summary(self, source: SourceName) -> tuple[int, date | None, date | None]:
        model = spec_for(source.value).model
        count = self._session.scalar(select(func.count()).select_from(model)) or 0
        if source is SourceName.ORDER_LINES:
            first, last = self._session.execute(
                select(func.min(Order.order_date), func.max(Order.order_date)).join(OrderLine, OrderLine.order_no == Order.order_no)
            ).one()
            return count, first, last
        column = _DATES.get(source)
        if column is None:
            return count, None, None
        first, last = self._session.execute(select(func.min(column), func.max(column))).one()
        return count, first, last
