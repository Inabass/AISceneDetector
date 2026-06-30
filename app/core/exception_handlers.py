import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_payload(
    *,
    error_code: str,
    message: str,
    detail: dict[str, Any] | None,
    recoverable: bool,
    suggested_action: str | None,
    request_id: str | None,
) -> dict[str, Any]:
    return {
        "data": None,
        "error": {
            "error_code": error_code,
            "message": message,
            "detail": detail,
            "recoverable": recoverable,
            "suggested_action": suggested_action,
            "request_id": request_id,
        },
        "request_id": request_id,
    }


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            error_code=exc.error_code,
            message=exc.message,
            detail=exc.detail,
            recoverable=exc.recoverable,
            suggested_action=exc.suggested_action,
            request_id=_request_id(request),
        ),
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(
            error_code="REQUEST_VALIDATION_ERROR",
            message="Request validation failed.",
            detail={"errors": exc.errors()},
            recoverable=True,
            suggested_action="Check the request body, path, and query parameters.",
            request_id=_request_id(request),
        ),
    )


async def http_error_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            detail=None,
            recoverable=400 <= exc.status_code < 500,
            suggested_action=None,
            request_id=_request_id(request),
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    logger.exception("Unhandled application error", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content=error_payload(
            error_code="INTERNAL_SERVER_ERROR",
            message="An internal error occurred.",
            detail=None,
            recoverable=False,
            suggested_action="Check the application log with the request_id.",
            request_id=request_id,
        ),
    )
