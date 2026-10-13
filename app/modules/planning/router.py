from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def status() -> dict:
    return {"module": "planning", "status": "pending"}


# PENDIENTE: ver docs/modulos.md para lo que debe hacer este módulo.
