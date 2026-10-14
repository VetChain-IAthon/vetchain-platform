"""Traduce los errores a HTTP con una sola forma: {"error": {"code", "message", "details"}}.

El dominio lanza errores de negocio sin saber de HTTP; aquí se convierten:
BusinessRuleError → 400, UnauthorizedError → 401, ForbiddenError → 403, NotFoundError → 404, ConflictError → 409.
El formato inválido lo detecta FastAPI → 422.
"""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.domain import (
    BusinessRuleError,
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)

STATUS_BY_ERROR: dict[type[DomainError], int] = {
    BusinessRuleError: 400,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
}

_HTTP_CODES = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed", 501: "not_implemented"}


def error_body(code: str, message: str, details: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def _status_for(error: DomainError) -> int:
    for error_type in type(error).__mro__:
        if error_type in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[error_type]
    return 400


async def _domain_error(_: Request, error: DomainError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(error, UnauthorizedError) else None
    return JSONResponse(error_body(error.code, error.message), status_code=_status_for(error), headers=headers)


async def _validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in item["loc"] if part != "body"), "message": item["msg"]}
        for item in error.errors()
    ]
    return JSONResponse(error_body("validation_error", "Los datos enviados no tienen el formato esperado.", details), 422)


async def _http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
    if isinstance(error.detail, dict) and "error" in error.detail:
        body = error.detail
    else:
        message = error.detail if isinstance(error.detail, str) else "Error."
        if error.status_code == 404 and message == "Not Found":
            message = "La ruta no existe."
        elif error.status_code == 405:
            message = "Método no permitido en esta ruta."
        body = error_body(_HTTP_CODES.get(error.status_code, "http_error"), message)
    return JSONResponse(body, status_code=error.status_code, headers=getattr(error, "headers", None))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
