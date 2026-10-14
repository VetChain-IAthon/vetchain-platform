"""Carga de los 7 CSV de Defontana (sin encabezados) con la política de campos vacíos.

Política (ver docs/base-de-datos.md):
- Texto opcional vacío ("" o solo espacios) se guarda NULL. Nunca "".
- Dato obligatorio vacío o inválido rechaza la fila y se cuenta con su motivo.
- Una FK que no existe en la tabla padre rechaza la fila (solo donde los datos reales la cumplen al 100 %).
- Columnas 100 % vacías, constantes o repetidas de otra tabla no se guardan.
- Nunca se rellena un dato faltante con promedios ni con datos de otra tabla.
- Upsert por clave (INSERT ... ON CONFLICT DO UPDATE). Nunca borra.
"""
import calendar
import csv
import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.core.database import Base
from app.infrastructure.db.source_models import (
    SOURCE_MODELS,
    Customer,
    Order,
    OrderLine,
    Product,
    Receipt,
    Salesperson,
    StockBalance,
)

Record = dict[str, Any]

TEXT, INT, DECIMAL, DATE, BOOL = "text", "int", "decimal", "date", "bool"
CHUNK_SIZE = 500
MAX_SAMPLES = 10


@dataclass(frozen=True)
class Field:
    index: int  # posición en el CSV, desde 0
    name: str
    kind: str = TEXT
    required: bool = True


@dataclass(frozen=True)
class SourceSpec:
    number: int  # número del archivo: 1_clientes.csv, mederi-1-ventas.csv, ...
    label: str
    model: type
    width: int
    fields: tuple[Field, ...]
    conflict_keys: tuple[str, ...]
    foreign_keys: tuple[tuple[str, type], ...] = ()
    derive: Callable[[Record], None] | None = None

    @property
    def table(self) -> str:
        return self.model.__tablename__


@dataclass
class SourceReport:
    table: str
    file: str = ""
    rows_read: int = 0
    rows_loaded: int = 0
    rejected: Counter = field(default_factory=Counter)
    rejected_samples: list[tuple[int, str]] = field(default_factory=list)
    warnings: Counter = field(default_factory=Counter)
    rejected_lines: list[tuple[int, str]] = field(default_factory=list)  # todas, para revisar una carga desde Ajustes

    @property
    def rows_rejected(self) -> int:
        return sum(self.rejected.values())

    def reject(self, line: int, reason: str) -> None:
        self.rejected[reason] += 1
        self.rejected_lines.append((line, reason))
        if len(self.rejected_samples) < MAX_SAMPLES:
            self.rejected_samples.append((line, reason))


# --- columnas derivadas -------------------------------------------------------------------------


def _tax_id_kind(record: Record) -> None:
    ruc = record["ruc"]
    if len(ruc) == 11 and ruc.startswith("20"):
        record["tax_id_kind"] = "company"
    elif len(ruc) == 11 and ruc[:2] in ("10", "15", "17"):
        record["tax_id_kind"] = "person"
    else:
        record["tax_id_kind"] = "other"


def _product_flags(record: Record) -> None:
    record["prefix"] = record["code"][:3]
    record["is_core_product"] = record["prefix"] == "MED"


def _order_flags(record: Record) -> None:
    record["is_dispatched"] = record["status_code"] == "T"


def _line_flags(record: Record) -> None:
    record["is_bonus"] = record["unit_price"] <= Decimal("0.01")


def _period_end(record: Record) -> None:
    year, month = record["year"], record["month"]
    if not 1 <= month <= 12:
        raise ValueError("month fuera de 1-12")
    record["period_end"] = date(year, month, calendar.monthrange(year, month)[1])


# --- mapa CSV → columna (cN = posición) ------------------------------------------------------------

SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(7, "vendedores", Salesperson, 5, (
        Field(0, "code"), Field(1, "name"), Field(2, "location", required=False), Field(4, "is_active", BOOL),
    ), ("code",)),
    SourceSpec(1, "clientes", Customer, 16, (
        Field(0, "ruc"), Field(1, "name"), Field(2, "address", required=False), Field(3, "phone", required=False),
        Field(4, "email", required=False), Field(5, "salesperson_code"), Field(7, "department_code", required=False),
        Field(8, "department", required=False), Field(9, "segment_code", required=False),
        Field(11, "condition_code", required=False), Field(14, "is_active", BOOL),
    ), ("ruc",), (("salesperson_code", Salesperson),), _tax_id_kind),
    SourceSpec(4, "productos", Product, 14, (
        Field(0, "code"), Field(1, "name"), Field(2, "alias", required=False), Field(3, "category_code"),
        Field(5, "unit_code"), Field(10, "is_active", BOOL),
    ), ("code",), (), _product_flags),
    SourceSpec(2, "pedidos", Order, 12, (
        Field(0, "order_no"), Field(1, "order_date", DATE), Field(2, "ruc"), Field(4, "salesperson_code"),
        Field(6, "channel_code"), Field(7, "subtotal", DECIMAL), Field(8, "discount", DECIMAL), Field(9, "tax", DECIMAL),
        Field(10, "total", DECIMAL), Field(11, "status_code", required=False),
    ), ("order_no",), (("ruc", Customer), ("salesperson_code", Salesperson)), _order_flags),
    SourceSpec(3, "detalle de pedidos", OrderLine, 14, (
        Field(0, "order_no"), Field(4, "line_no", INT), Field(5, "product_code"), Field(7, "unit_code"),
        Field(8, "quantity", DECIMAL), Field(9, "quantity_dispatched", DECIMAL), Field(11, "unit_price", DECIMAL),
        Field(12, "discount_pct", DECIMAL), Field(13, "line_total", DECIMAL),
    ), ("order_no", "line_no", "dup_seq"), (("order_no", Order), ("product_code", Product)), _line_flags),
    SourceSpec(5, "kardex", StockBalance, 6, (
        Field(0, "warehouse_code"), Field(1, "year", INT), Field(2, "month", INT), Field(3, "product_code"),
        Field(4, "product_name", required=False), Field(5, "balance", DECIMAL),
    ), ("warehouse_code", "year", "month", "product_code"), (), _period_end),
    SourceSpec(6, "cobros", Receipt, 12, (
        Field(0, "receipt_no"), Field(1, "receipt_date", DATE), Field(2, "ruc"), Field(4, "type_code"),
        Field(5, "document_no"), Field(6, "code_c6"), Field(7, "payment_method_code"), Field(8, "code_c8"),
        Field(9, "reference_no", required=False), Field(10, "amount", DECIMAL), Field(11, "applied_date", DATE),
    ), ("receipt_no", "document_no"), (("ruc", Customer),)),
)


# --- lectura y validación (sin base de datos) ------------------------------------------------------


def _convert(kind: str, value: str) -> Any:
    if kind == TEXT:
        return value
    if kind == INT:
        return int(value)
    if kind == DECIMAL:
        try:
            return Decimal(value)
        except InvalidOperation:
            raise ValueError(value) from None
    if kind == DATE:
        return date.fromisoformat(value)
    if value not in ("0", "1"):
        raise ValueError(value)
    return value == "1"


def parse_rows(
    spec: SourceSpec,
    rows: Iterable[list[str]],
    parent_keys: dict[str, set[str]] | None = None,
) -> tuple[list[Record], SourceReport]:
    """Convierte las filas del CSV en registros listos para el upsert. `parent_keys`: tabla padre → claves existentes."""
    parent_keys = parent_keys or {}
    report = SourceReport(spec.table)
    records: list[Record] = []
    seen_keys: set[tuple] = set()
    line_seq: Counter = Counter()
    for line, row in enumerate(rows, start=1):
        report.rows_read += 1
        if len(row) != spec.width:
            report.reject(line, f"se esperaban {spec.width} columnas")
            continue
        record: Record = {}
        problem = None
        for fld in spec.fields:
            raw = row[fld.index].strip()
            if not raw:
                if fld.required:
                    problem = f"falta {fld.name}"
                    break
                record[fld.name] = None
                report.warnings[f"{fld.name} vacío"] += 1
                continue
            try:
                record[fld.name] = _convert(fld.kind, raw)
            except ValueError:
                problem = f"{fld.name} inválido"
                break
        if problem is None:
            for column, parent in spec.foreign_keys:
                if parent.__tablename__ in parent_keys and record[column] not in parent_keys[parent.__tablename__]:
                    problem = f"{column} no existe en {parent.__tablename__}"
                    break
        if problem is None and spec.derive is not None:
            try:
                spec.derive(record)
            except ValueError as error:
                problem = str(error)
        if problem is not None:
            report.reject(line, problem)
            continue
        if spec.model is OrderLine:
            pair = (record["order_no"], record["line_no"])
            record["dup_seq"] = line_seq[pair]
            line_seq[pair] += 1
            if record["dup_seq"]:
                report.warnings["línea repetida (pedido, línea)"] += 1
        if spec.model is StockBalance and record["balance"] < 0:
            report.warnings["saldo negativo"] += 1
        key = tuple(record[name] for name in spec.conflict_keys)
        if key in seen_keys:
            report.reject(line, "clave repetida en el archivo")
            continue
        seen_keys.add(key)
        records.append(record)
    return records, report


def read_csv(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.reader(file))


_FILE_NUMBER = re.compile(r"(?<![0-9])([1-7])(?=[_-])")


def find_files(directory: Path) -> dict[int, Path]:
    """Ubica cada CSV por su número: acepta 1_clientes.csv o mederi-1-ventas.csv."""
    found: dict[int, list[Path]] = {}
    for path in sorted(directory.glob("*.csv")):
        match = _FILE_NUMBER.search(path.name)
        if match:
            found.setdefault(int(match.group(1)), []).append(path)
    missing = [spec.number for spec in SPECS if spec.number not in found]
    repeated = [number for number, paths in found.items() if len(paths) > 1]
    if missing or repeated:
        raise FileNotFoundError(
            f"En {directory} faltan los archivos {missing} o hay números repetidos {repeated}. "
            "Se esperan 7 CSV numerados del 1 al 7."
        )
    return {number: paths[0] for number, paths in found.items()}


# --- escritura -----------------------------------------------------------------------------------


def upsert(session: Session, model: type, records: list[Record], conflict_keys: tuple[str, ...]) -> int:
    """INSERT ... ON CONFLICT DO UPDATE en PostgreSQL y SQLite. Nunca borra."""
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        insert = postgresql.insert
    elif dialect == "sqlite":
        insert = sqlite.insert
    else:
        raise NotImplementedError(f"Upsert no soportado para {dialect}.")
    for start in range(0, len(records), CHUNK_SIZE):
        chunk = records[start:start + CHUNK_SIZE]
        statement = insert(model).values(chunk)
        updates = {column: statement.excluded[column] for column in chunk[0] if column not in conflict_keys}
        session.execute(statement.on_conflict_do_update(index_elements=list(conflict_keys), set_=updates))
    return len(records)


def _parent_keys(session: Session, spec: SourceSpec) -> dict[str, set[str]]:
    keys = {}
    for column, parent in spec.foreign_keys:
        (pk,) = parent.__table__.primary_key.columns
        keys[parent.__tablename__] = set(session.scalars(select(pk)))
    return keys


def validate_source(session: Session, spec: SourceSpec, rows: Iterable[list[str]]) -> SourceReport:
    """Valida las filas contra la base actual (claves foráneas incluidas) sin escribir nada."""
    return parse_rows(spec, rows, _parent_keys(session, spec))[1]


def spec_for(table: str) -> SourceSpec:
    return next(spec for spec in SPECS if spec.table == table)


def load_source(session: Session, spec: SourceSpec, rows: Iterable[list[str]]) -> SourceReport:
    records, report = parse_rows(spec, rows, _parent_keys(session, spec))
    report.rows_loaded = upsert(session, spec.model, records, spec.conflict_keys) if records else 0
    return report


def load_directory(session: Session, directory: Path) -> list[SourceReport]:
    """Crea las tablas de Defontana si no existen y carga los 7 CSV en orden de dependencias."""
    files = find_files(directory)
    Base.metadata.create_all(session.get_bind(), tables=[model.__table__ for model in SOURCE_MODELS])
    reports = []
    for spec in SPECS:
        report = load_source(session, spec, read_csv(files[spec.number]))
        report.file = files[spec.number].name
        session.commit()
        reports.append(report)
    return reports
