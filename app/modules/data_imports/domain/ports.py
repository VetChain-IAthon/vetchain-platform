from collections.abc import Iterable
from typing import BinaryIO, Protocol

from app.core.application import Page, Paging
from app.core.domain import DataOrigin
from app.modules.data_imports.domain.entities import DataImport
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
    """Guarda las filas válidas hasta que se confirme la carga."""

    def put(self, import_id: int, records: list[Record]) -> None: ...

    def take(self, import_id: int) -> list[Record]: ...

    def discard(self, import_id: int) -> None: ...


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
