from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from app.core.domain import BusinessRuleError, ConflictError, DataOrigin
from app.modules.data_imports.domain.sources import SourceName


class ImportStatus(StrEnum):
    STAGED = "staged"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


IMPORT_ORIGINS = frozenset({DataOrigin.REAL, DataOrigin.SYNTHETIC, DataOrigin.SIMULATED})


@dataclass(frozen=True)
class RowError:
    line: int
    message: str


@dataclass(frozen=True)
class DataImport:
    """Raíz del agregado. Confirmar actualiza e inserta; nunca borra."""

    source: SourceName
    origin: DataOrigin
    rows_read: int
    rows_with_error: int
    created_at: datetime
    status: ImportStatus = ImportStatus.STAGED
    decided_at: datetime | None = None
    errors: tuple[RowError, ...] = ()
    id: int | None = None
    file_name: str = ""
    rows_loaded: int | None = None  # filas escritas al confirmar (actualizadas o insertadas)
    created_by: int | None = None

    def __post_init__(self) -> None:
        if self.origin not in IMPORT_ORIGINS:
            raise BusinessRuleError("Una carga debe ser real, synthetic o simulated.", "invalid_import_origin")
        if not 0 <= self.rows_with_error <= self.rows_read:
            raise BusinessRuleError("Las filas con error no cuadran con las filas leídas.", "invalid_row_counts")

    @property
    def valid_rows(self) -> int:
        return self.rows_read - self.rows_with_error

    def confirm(self, now: datetime, rows_loaded: int | None = None) -> "DataImport":
        ImportStateMachine.ensure(self.status, ImportStatus.CONFIRMED)
        if self.valid_rows == 0:
            raise BusinessRuleError("No hay filas válidas para cargar.", "no_valid_rows")
        return replace(self, status=ImportStatus.CONFIRMED, decided_at=now, rows_loaded=rows_loaded)

    def cancel(self, now: datetime) -> "DataImport":
        ImportStateMachine.ensure(self.status, ImportStatus.CANCELLED)
        return replace(self, status=ImportStatus.CANCELLED, decided_at=now)


class ImportStateMachine:
    """staged → confirmed | cancelled. Nada más."""

    _ALLOWED = {ImportStatus.STAGED: {ImportStatus.CONFIRMED, ImportStatus.CANCELLED}}

    @classmethod
    def ensure(cls, current: ImportStatus, target: ImportStatus) -> None:
        if target not in cls._ALLOWED.get(current, set()):
            raise ConflictError("Solo una carga en revisión se puede confirmar o cancelar.", "import_not_staged")
