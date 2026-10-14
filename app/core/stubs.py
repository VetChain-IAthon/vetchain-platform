from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException

from app.core.errors import error_body

NOT_IMPLEMENTED = {501: {"description": "Endpoint del contrato aún no construido"}}


def pending() -> None:
    """Para endpoints del contrato aún no construidos: responden 501 con la forma de error estándar."""
    raise HTTPException(
        status_code=501,
        detail=error_body("not_implemented", "Este endpoint todavía no está construido."),
    )


def add_pending_route(router: APIRouter, method: str, path: str, roles: Sequence[str], summary: str) -> None:
    """Registra una ruta del contrato que exige sesión y rol, y responde 501 hasta que se construya."""
    from app.core.auth import require_role  # import tardío: auth depende de errors

    def endpoint() -> None:
        pending()

    endpoint.__name__ = f"pending_{method.lower()}_{path.strip('/').replace('/', '_').replace('-', '_').replace('{', '').replace('}', '')}"
    router.add_api_route(
        path,
        endpoint,
        methods=[method],
        summary=f"{summary} (pendiente)",
        dependencies=[Depends(require_role(*roles))],
        responses=NOT_IMPLEMENTED,
        status_code=501,
    )
