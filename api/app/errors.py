import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

from app.logging import REQUEST_ID_HEADER, request_id_var

logger = logging.getLogger(__name__)

HTTP_CODES = {
    401: "AUTH_INVALID",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
}


ERROR_DESCRIPTIONS = {
    401: "Missing or invalid credentials",
    403: "The token is valid, but its user is not the owner",
    404: "No such record",
    409: "The request conflicts with the current state",
    422: "The request is not valid",
    503: "A required setting is missing on the server",
}


class ErrorDetail(BaseModel):
    code: str = Field(
        description="Stable and machine-readable; branch on this.", examples=["NOT_FOUND"]
    )
    message: str = Field(
        description="For a person to read. The wording may change.",
        examples=["Application not found"],
    )


class ErrorResponse(BaseModel):
    """The body of every error response, whatever the status code."""

    error: ErrorDetail


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """The `responses=` of a route or router, so the OpenAPI document shows the error shape."""
    return {
        status: {"model": ErrorResponse, "description": ERROR_DESCRIPTIONS[status]}
        for status in statuses
    }


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def error_response(
    code: str, message: str, status: int, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.code, exc.message, exc.status)

    @app.exception_handler(HTTPException)
    def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        code = HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        return error_response(code, str(exc.detail), exc.status_code, exc.headers)

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        return error_response("VALIDATION", f"{location}: {first['msg']}", 422)

    @app.exception_handler(Exception)
    def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        # This handler runs outside the request id middleware, so it sets the header itself.
        request_id = request_id_var.get()
        headers = {REQUEST_ID_HEADER: request_id} if request_id else None
        return error_response("INTERNAL", "Internal server error", 500, headers)
