"""Consulta y revisión humana de un escenario ilustrativo de importación."""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.application import MANAGER
from app.core.auth import require_role
from app.core.database import get_db
from app.core.domain import ConflictError, NotFoundError
from app.modules.import_planning.infrastructure.orm import ImportLaboratoryRow, ImportSuggestionRow
from app.modules.import_planning.interface.schemas import DecisionIn, ImportPlanOut, LaboratoryOut, SuggestionOut

router = APIRouter(tags=["planificación de importación"], dependencies=[Depends(require_role(MANAGER))])


@router.get("/import-suggestions", response_model=ImportPlanOut)
def list_import_suggestions(db: Session = Depends(get_db)):
    """Escenario persistido de cuatro laboratorios. Todas las cifras son de ejemplo."""
    labs = db.scalars(select(ImportLaboratoryRow).order_by(ImportLaboratoryRow.id)).all()
    suggestions = db.scalars(select(ImportSuggestionRow).order_by(ImportSuggestionRow.id)).all()
    by_lab: dict[int, list[ImportSuggestionRow]] = {lab.id: [] for lab in labs}
    for row in suggestions:
        by_lab[row.laboratory_id].append(row)
    today = date.today()
    return ImportPlanOut(laboratories=[LaboratoryOut.from_rows(lab, by_lab[lab.id], today) for lab in labs])


@router.patch("/import-suggestions/{suggestion_id}", response_model=SuggestionOut)
def decide_import_suggestion(suggestion_id: int, body: DecisionIn, db: Session = Depends(get_db)):
    """Guarda una revisión de la simulación; no crea ni autoriza compras."""
    row = db.get(ImportSuggestionRow, suggestion_id)
    if row is None:
        raise NotFoundError("No existe esa sugerencia.", "suggestion_not_found")
    if row.decision == body.decision:
        raise ConflictError("La sugerencia ya tiene esa decisión.", "already_decided")
    if row.decision != "pending" and body.decision != "pending":
        raise ConflictError("Vuelve a pendiente antes de cambiar la decisión.", "already_decided")
    row.decision = body.decision
    db.commit()
    db.refresh(row)
    return SuggestionOut.from_row(row, date.today())
