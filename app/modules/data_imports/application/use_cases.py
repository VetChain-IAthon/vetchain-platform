"""Casos de uso de data_imports: subir un CSV (se valida, no se aplica), revisar y confirmar o cancelar.

Confirmar actualiza e inserta en las tablas de Defontana con las mismas reglas que la carga inicial; nunca borra.
"""
import csv
import io
from dataclasses import dataclass
from datetime import date

from app.core.application import Page, Paging, SessionUser
from app.core.domain import BusinessRuleError, Clock, DataOrigin, NotFoundError, UnitOfWork
from app.modules.data_imports.domain.entities import DataImport, ImportStatus
from app.modules.data_imports.domain.ports import DataImportRepository, SourceLoader, SourceStats, StagingStore
from app.modules.data_imports.domain.sources import LOAD_ORDER, SOURCES, DataSource, SourceName

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_STORED_ERRORS = 200


@dataclass(frozen=True)
class SourceSummary:
    source: DataSource
    rows_in_db: int
    first_date: date | None
    last_date: date | None
    last_import: DataImport | None


class ListDataSources:
    """Los 7 archivos: qué contienen, cuántas filas hay en la base, su período y la última carga confirmada."""

    def __init__(self, imports: DataImportRepository, stats: SourceStats, uow: UnitOfWork) -> None:
        self.imports, self.stats, self.uow = imports, stats, uow

    def execute(self) -> list[SourceSummary]:
        with self.uow:
            last = self.imports.last_confirmed()
            return [SourceSummary(SOURCES[name], *self.stats.summary(name), last.get(name)) for name in LOAD_ORDER]


@dataclass(frozen=True)
class StageImportCommand:
    source: str
    file_name: str
    content: bytes
    origin: str = DataOrigin.REAL.value


def _read_rows(content: bytes) -> list[list[str]]:
    if not content.strip():
        raise BusinessRuleError("El archivo está vacío.", "empty_file")
    if len(content) > MAX_FILE_BYTES:
        raise BusinessRuleError("El archivo pesa más de 25 MB. Divídelo en partes.", "file_too_large")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")  # Excel en Windows suele guardar CSV en Latin-1
    sample = text[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if any(value.strip() for value in row)]


class StageImport:
    """Lee el CSV, revisa los encabezados y valida cada fila. Guarda la carga en revisión; no toca los datos."""

    def __init__(self, imports: DataImportRepository, staging: StagingStore, loader: SourceLoader, clock: Clock,
                 uow: UnitOfWork) -> None:
        self.imports, self.staging, self.loader, self.clock, self.uow = imports, staging, loader, clock, uow

    def execute(self, command: StageImportCommand, user: SessionUser) -> DataImport:
        try:
            source = SOURCES[SourceName(command.source)]
        except ValueError:
            raise BusinessRuleError("Elige uno de los 7 archivos de Mederi.", "unknown_source") from None
        rows = _read_rows(command.content)
        source.check_headers(rows[0])
        data_rows = rows[1:]
        source.restore_leading_zeros(data_rows)
        if not data_rows:
            raise BusinessRuleError("El archivo solo trae encabezados; no hay filas para cargar.", "empty_file")
        with self.uow:
            rows_read, errors = self.loader.validate(source.name, data_rows)
            data_import = DataImport(
                source=source.name, origin=DataOrigin(command.origin), rows_read=rows_read, rows_with_error=len(errors),
                created_at=self.clock.now(), errors=tuple(errors[:MAX_STORED_ERRORS]),
                file_name=command.file_name[:200], created_by=user.id,
            )
            data_import = self.imports.add(data_import)
            self.staging.put(data_import.id, data_rows)
            self.uow.commit()
            return data_import


MAX_PREVIEW_ROWS = 500


@dataclass(frozen=True)
class PreviewRow:
    line: int  # línea del archivo (la 1 son los encabezados)
    values: tuple[str, ...]
    status: str  # new · update · error
    message: str | None = None


@dataclass(frozen=True)
class ImportPreview:
    columns: tuple[str, ...]
    rows: tuple[PreviewRow, ...]
    new_rows: int
    updated_rows: int


class PreviewImport:
    """Qué hará la carga fila por fila mientras está en revisión: agregar, actualizar o descartar por error."""

    def __init__(self, imports: DataImportRepository, staging: StagingStore, loader: SourceLoader, uow: UnitOfWork) -> None:
        self.imports, self.staging, self.loader, self.uow = imports, staging, loader, uow

    def execute(self, import_id: int) -> ImportPreview | None:
        with self.uow:
            data_import = _get(self.imports, import_id)
            if data_import.status is not ImportStatus.STAGED:
                return None
            source = SOURCES[data_import.source]
            rows = self.staging.take(import_id)
            errors = {e.line: e.message for e in data_import.errors}
            existing = self.loader.existing_lines(source.name, rows)
            preview, new, updated = [], 0, 0
            for line, row in enumerate(rows, start=1):
                if line in errors or (len(errors) >= MAX_STORED_ERRORS and line > max(errors)):
                    status = "error"
                elif line in existing:
                    status, updated = "update", updated + 1
                else:
                    status, new = "new", new + 1
                if len(preview) < MAX_PREVIEW_ROWS:
                    preview.append(PreviewRow(line + 1, source.preview_values(row), status, errors.get(line)))
            return ImportPreview(source.preview_columns, tuple(preview), new, updated)


class ListImports:
    def __init__(self, imports: DataImportRepository, uow: UnitOfWork) -> None:
        self.imports, self.uow = imports, uow

    def execute(self, paging: Paging) -> Page[DataImport]:
        with self.uow:
            return self.imports.list(paging)


class GetImport:
    def __init__(self, imports: DataImportRepository, uow: UnitOfWork) -> None:
        self.imports, self.uow = imports, uow

    def execute(self, import_id: int) -> DataImport:
        with self.uow:
            return _get(self.imports, import_id)


class DecideImport:
    """Confirmar escribe las filas válidas (actualiza e inserta, nunca borra); cancelar las descarta."""

    def __init__(self, imports: DataImportRepository, staging: StagingStore, loader: SourceLoader, clock: Clock,
                 uow: UnitOfWork) -> None:
        self.imports, self.staging, self.loader, self.clock, self.uow = imports, staging, loader, clock, uow

    def execute(self, import_id: int, action: str) -> DataImport:
        with self.uow:
            data_import = _get(self.imports, import_id)
            if action == "confirm":
                data_import.confirm(self.clock.now())  # lanza si no se puede confirmar, antes de escribir nada
                loaded = self.loader.load(data_import.source, self.staging.take(import_id))
                data_import = data_import.confirm(self.clock.now(), loaded)
            elif action == "cancel":
                data_import = data_import.cancel(self.clock.now())
            else:
                raise BusinessRuleError("La acción debe ser confirm o cancel.", "invalid_action")
            self.imports.save(data_import)
            self.staging.discard(import_id)
            self.uow.commit()
            return data_import


def _get(imports: DataImportRepository, import_id: int) -> DataImport:
    found = imports.get(import_id)
    if found is None:
        raise NotFoundError("No existe esa carga.", "import_not_found")
    return found
