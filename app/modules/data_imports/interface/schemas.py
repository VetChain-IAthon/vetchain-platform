from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.data_imports.application import use_cases as uc
from app.modules.data_imports.domain.entities import DataImport


class LastImportOut(BaseModel):
    id: int
    decided_at: datetime | None
    origin: str
    rows_loaded: int | None


class DataSourceOut(BaseModel):
    source: str = Field(description="customers, salespeople, products, orders, order_lines, stock_balances o receipts")
    number: int
    description: str
    file_name: str = Field(description="Nombre sugerido del archivo, como los CSV originales")
    headers: list[str] = Field(description="Encabezados que debe traer la primera fila, en este orden")
    rows_in_db: int
    first_date: date | None
    last_date: date | None
    last_import: LastImportOut | None

    @classmethod
    def from_result(cls, item: uc.SourceSummary) -> "DataSourceOut":
        last = item.last_import
        return cls(source=item.source.name.value, number=item.source.number, description=item.source.description,
                   file_name=item.source.file_name, headers=list(item.source.headers), rows_in_db=item.rows_in_db,
                   first_date=item.first_date, last_date=item.last_date,
                   last_import=LastImportOut(id=last.id, decided_at=last.decided_at, origin=last.origin.value,
                                             rows_loaded=last.rows_loaded) if last else None)


class DataSourcesOut(BaseModel):
    items: list[DataSourceOut]


class RowErrorOut(BaseModel):
    line: int = Field(description="Línea del archivo (la 2 es la primera fila de datos, después de los encabezados)")
    message: str


class DataImportOut(BaseModel):
    id: int
    source: str
    file_name: str
    origin: str
    status: Literal["staged", "confirmed", "cancelled"]
    rows_read: int
    rows_with_error: int
    valid_rows: int
    rows_loaded: int | None
    errors: list[RowErrorOut] = Field(description="Hasta 200 errores por línea")
    created_at: datetime
    decided_at: datetime | None
    preview: "ImportPreviewOut | None" = Field(None, description="Solo mientras la carga está en revisión")

    @classmethod
    def from_domain(cls, item: DataImport, preview: "uc.ImportPreview | None" = None) -> "DataImportOut":
        return cls(id=item.id, source=item.source.value, file_name=item.file_name, origin=item.origin.value,
                   status=item.status.value, rows_read=item.rows_read, rows_with_error=item.rows_with_error,
                   valid_rows=item.valid_rows, rows_loaded=item.rows_loaded,
                   # El validador cuenta desde la primera fila de datos; en el archivo es una línea más (encabezados).
                   errors=[RowErrorOut(line=e.line + 1, message=e.message) for e in item.errors],
                   created_at=item.created_at, decided_at=item.decided_at,
                   preview=ImportPreviewOut.from_result(preview) if preview else None)


class PreviewRowOut(BaseModel):
    line: int
    values: list[str]
    status: Literal["new", "update", "error"]
    message: str | None


class ImportPreviewOut(BaseModel):
    columns: list[str] = Field(description="Encabezados de las columnas que identifican cada fila")
    rows: list[PreviewRowOut] = Field(description="Hasta 500 filas, en el orden del archivo")
    new_rows: int = Field(description="Filas válidas que se agregarán")
    updated_rows: int = Field(description="Filas válidas que actualizan un registro existente")

    @classmethod
    def from_result(cls, preview: uc.ImportPreview) -> "ImportPreviewOut":
        return cls(columns=list(preview.columns), new_rows=preview.new_rows, updated_rows=preview.updated_rows,
                   rows=[PreviewRowOut(line=r.line, values=list(r.values), status=r.status, message=r.message) for r in preview.rows])


class DataImportPageOut(BaseModel):
    items: list[DataImportOut]
    total: int
    page: int
    per_page: int


class DataImportDecisionIn(BaseModel):
    action: Literal["confirm", "cancel"]


DataImportOut.model_rebuild()
