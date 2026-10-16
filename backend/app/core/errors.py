"""Stable API error response helpers and exception handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import log_event


def error_payload(
    *,
    code: str,
    message: str,
    request_id: str,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the standard public error envelope."""
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "details": details or [],
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Register sanitized handlers for expected and unexpected API errors."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        safe_details = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "value_error")),
            }
            for error in exc.errors()
        ]
        log_event(
            logging.INFO,
            "request_validation_failed",
            request_id=request_id,
            path=request.url.path,
            error_count=len(safe_details),
        )
        return JSONResponse(
            status_code=422,
            content=error_payload(
                code="request_validation_error",
                message="The request did not pass validation.",
                request_id=request_id,
                details=safe_details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        # Keep public messages controlled; never serialize arbitrary exception objects.
        safe_messages = {
            400: "The request could not be processed.",
            401: "Authentication is required.",
            403: "You are not allowed to perform this action.",
            404: "The requested resource was not found.",
            405: "The requested method is not allowed.",
            409: "The request conflicts with the current resource state.",
            413: "The submitted content is too large.",
            415: "The submitted media type is not supported.",
            429: "Too many requests.",
        }
        message = safe_messages.get(exc.status_code, "The request could not be processed.")
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=error_payload(
                code=f"http_{exc.status_code}",
                message=message,
                request_id=request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        log_event(
            logging.ERROR,
            "unhandled_request_error",
            request_id=request_id,
            path=request.url.path,
            exception_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=error_payload(
                code="internal_server_error",
                message="An unexpected error occurred.",
                request_id=request_id,
            ),
        )
