"""Единый формат ошибок API: {"error": {kind, code, message, details}} (ФТ-16)."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError

HTTP_STATUS = {
    "validation": 422,
    "forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "unavailable": 503,
}


def error_response(kind: str, code: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_STATUS.get(kind, 400),
        content={"error": {"kind": kind, "code": code, "message": message, "details": details or {}}},
    )


def install(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError):
        details = {k: v for k, v in exc.details.items() if k != "reason"}  # без технических подробностей
        return error_response(exc.kind, exc.code, exc.message, details)

    @app.exception_handler(RequestValidationError)
    async def _request(_: Request, exc: RequestValidationError):
        return error_response("validation", "bad_request", "Некорректный запрос: проверьте переданные данные")
