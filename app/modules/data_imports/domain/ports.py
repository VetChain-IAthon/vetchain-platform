from collections.abc import Iterable
from datetime import date
from typing import BinaryIO, Protocol

from app.core.application import Page, Paging
from app.core.domain import DataOrigin
from app.modules.data_imports.domain.entities import DataImport, RowError
from app.modules.data_imports.domain.sources import Record, SourceName


class DataImportRepository(Protocol):
    def add(self, data_import: DataImport) -> DataImport: ...

    def get(self, import_id: int) -> DataImport | None: ...

    def list(self, paging: Paging) -> Page[DataImport]: ...

    def save(self, data_import: DataImport) -> None: ...

    def last_confirmed(self) -> dict[SourceName, DataImport]: ...


class CsvReader(Protocol):
    def rows(self, file: BinaryIO) -> Iterable[tuple[int, list[str]]]:
        """(número de línea, valores). Los CSV no traen encabezado."""
        ...


class StagingStore(Protocol):
    """Guarda las filas del CSV (sin encabezado) hasta que se confirme o cancele la carga."""

    def put(self, import_id: int, rows: list[list[str]]) -> None: ...

    def take(self, import_id: int) -> list[list[str]]: ...

    def discard(self, import_id: int) -> None: ...


class SourceLoader(Protocol):
    """Valida y escribe las filas de una fuente con las mismas reglas que la carga inicial de los CSV."""

    def validate(self, source: SourceName, rows: list[list[str]]) -> tuple[int, list[RowError]]:
        """(filas leídas, errores por línea; la línea 1 es la primera fila de datos). No escribe nada."""
        ...

    def existing_lines(self, source: SourceName, rows: list[list[str]]) -> set[int]:
        """Líneas (desde 1, primera fila de datos) cuya clave ya existe en la base: al confirmar se actualizan."""
        ...

    def load(self, source: SourceName, rows: list[list[str]]) -> int:
        """Actualiza e inserta; nunca borra. Devuelve las filas escritas."""
        ...


class SourceStats(Protocol):
    def summary(self, source: SourceName) -> tuple[int, date | None, date | None]:
        """(filas en la base, primera fecha, última fecha); fechas None si la fuente no tiene fechas."""
        ...


class SourceDataWriter(Protocol):
    def upsert(self, source: SourceName, records: list[Record]) -> int:
        """Actualiza e inserta; nunca borra. Devuelve las filas escritas."""
        ...


class DataOriginRegistry(Protocol):
    def set(self, source: SourceName, origin: DataOrigin) -> None: ...

    def get(self, source: SourceName) -> DataOrigin | None: ...


class ConversionNotifier(Protocol):
    def orders_confirmed(self) -> None:
        """Avisa a quotations para enlazar conversiones y vencer cotizaciones."""
        ...
