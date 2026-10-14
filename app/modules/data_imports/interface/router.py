from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.core.application import MANAGER, Paging, SessionUser
from app.core.auth import require_role
from app.modules.data_imports.application import use_cases as uc
from app.modules.data_imports.interface import dependencies as deps
from app.modules.data_imports.interface.schemas import (
    DataImportDecisionIn,
    DataImportOut,
    DataImportPageOut,
    DataSourceOut,
    DataSourcesOut,
)

router = APIRouter(tags=["carga de datos"])
manager = require_role(MANAGER)

SourceParam = Literal["customers", "salespeople", "products", "orders", "order_lines", "stock_balances", "receipts"]


@router.get("/data-sources", response_model=DataSourcesOut)
def list_data_sources(_: SessionUser = Depends(manager), use_case: uc.ListDataSources = Depends(deps.get_list_sources)):
    """Los 7 archivos: encabezados esperados, filas en la base, período y última carga confirmada."""
    return DataSourcesOut(items=[DataSourceOut.from_result(item) for item in use_case.execute()])


@router.post("/data-imports", response_model=DataImportOut, status_code=201)
async def stage_import(
    source: SourceParam = Form(...),
    file: UploadFile = File(..., description="CSV con encabezados (ver /data-sources)"),
    origin: Literal["real", "synthetic", "simulated"] = Form("real"),
    user: SessionUser = Depends(manager),
    use_case: uc.StageImport = Depends(deps.get_stage_import),
    preview: uc.PreviewImport = Depends(deps.get_preview_import),
):
    """Sube un CSV: se revisan los encabezados y se valida cada fila. Queda en revisión; no se aplica todavía."""
    content = await file.read(uc.MAX_FILE_BYTES + 1)
    staged = use_case.execute(uc.StageImportCommand(source, file.filename or "archivo.csv", content, origin), user)
    return DataImportOut.from_domain(staged, preview.execute(staged.id))


@router.get("/data-imports", response_model=DataImportPageOut)
def list_imports(
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
    _: SessionUser = Depends(manager), use_case: uc.ListImports = Depends(deps.get_list_imports),
):
    """Cargas anteriores, de la más reciente a la más antigua."""
    result = use_case.execute(Paging(page, per_page))
    return DataImportPageOut(items=[DataImportOut.from_domain(i) for i in result.items], total=result.total, page=result.page,
                             per_page=result.per_page)


@router.get("/data-imports/{import_id}", response_model=DataImportOut)
def get_import(
    import_id: int, _: SessionUser = Depends(manager), use_case: uc.GetImport = Depends(deps.get_get_import),
    preview: uc.PreviewImport = Depends(deps.get_preview_import),
):
    """Revisión de una carga: filas leídas, válidas, errores por línea y, en revisión, qué pasará con cada fila."""
    return DataImportOut.from_domain(use_case.execute(import_id), preview.execute(import_id))


@router.patch("/data-imports/{import_id}", response_model=DataImportOut)
def decide_import(
    import_id: int, body: DataImportDecisionIn,
    _: SessionUser = Depends(manager), use_case: uc.DecideImport = Depends(deps.get_decide_import),
):
    """Confirmar escribe las filas válidas (actualiza e inserta, nunca borra). Cancelar las descarta."""
    return DataImportOut.from_domain(use_case.execute(import_id, body.action))
