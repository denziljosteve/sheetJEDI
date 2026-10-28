"""Consistent API error envelope and application exceptions."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that map directly to an API response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_body(
    code: str,
    message: str,
    request_id: str | None = None,
    details: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    if request_id:
        error["request_id"] = request_id
    return {"error": error}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, _request_id(request), exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Trim noisy validation output; never echo large payloads back.
        details = []
        for err in exc.errors()[:10]:
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            details.append({"field": loc, "message": err.get("msg", "invalid")})
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error",
                "Request validation failed.",
                _request_id(request),
                details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body("http_error", str(exc.detail), _request_id(request)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log internally with traceback; return a generic message only.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body(
                "internal_error",
                "An internal error occurred. Check the server logs for details.",
                _request_id(request) or uuid.uuid4().hex,
            ),
        )
