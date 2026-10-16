"""Datos de ejemplo para las secciones que esperan costos, lotes, facturas o el registro de alertas."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.application import MANAGER, SALESPERSON
from app.core.auth import require_role
from app.core.database import get_db
from app.modules.simulations.infrastructure.orm import SimulatedSectionRow
from app.modules.simulations.interface.schemas import SimulatedSectionsOut

# Gerencia y vendedores: el vendedor ve la cobranza simulada de sus clientes en Hoy.
router = APIRouter(tags=["datos simulados"], dependencies=[Depends(require_role(MANAGER, SALESPERSON))])


@router.get("/simulated-sections", response_model=SimulatedSectionsOut)
def list_simulated_sections(db: Session = Depends(get_db)):
    """Todas las secciones simuladas. La interfaz las muestra con la etiqueta «Simulado»."""
    rows = db.scalars(select(SimulatedSectionRow).order_by(SimulatedSectionRow.key)).all()
    return SimulatedSectionsOut(sections={row.key: row.payload for row in rows})
