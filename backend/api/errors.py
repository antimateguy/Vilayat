"""One error format for the whole API.

Every error response has the same shape, so a client needs one piece of error
handling: {"error": {"code", "message", "request_id", "details"}}.
"""

import logging
import math
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

from api.context import current_request_id
from cities.registry import UnknownCityError
from ports.embedder import EmbedderUnavailableError
from ports.llm import LLMUnavailableError
from ports.usage import DailyLimitReachedError
from services.errors import InvalidRequestError, NotFoundError

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    field: str = Field(examples=["max_commute_minutes"])
    problem: str = Field(examples=["Input should be less than or equal to 180"])


class ErrorBody(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["no campus with id 999"])
    request_id: str = Field(
        description="Also sent as the X-Request-ID header; quote it when reporting a problem."
    )
    details: list[ErrorDetail] = Field(
        default_factory=list, description="One entry per invalid field, for validation errors."
    )


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code, message=message, request_id=current_request_id(), details=details or []
        )
    )
    return JSONResponse(body.model_dump(), status_code=status_code, headers=headers)


# For the OpenAPI documentation of each route.
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorResponse,
        "description": "The city, campus, area or employer does not exist.",
    }
}
INVALID: dict[int | str, dict[str, Any]] = {
    422: {
        "model": ErrorResponse,
        "description": "A parameter is missing, malformed or out of range.",
    }
}
AI_UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    503: {
        "model": ErrorResponse,
        "description": "The language model is switched off or did not answer (code "
        "`ai_unavailable`), or its free daily allowance is used up (code `ai_daily_limit`, "
        "with Retry-After). Every endpoint that does not need it still works.",
    }
}
COMMON_ERRORS: dict[int | str, dict[str, Any]] = {
    429: {"model": ErrorResponse, "description": "Too many requests; see the Retry-After header."},
    500: {
        "model": ErrorResponse,
        "description": "Unexpected error; the request ID identifies it in the logs.",
    },
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    @app.exception_handler(UnknownCityError)
    async def not_found(_: Request, error: LookupError) -> JSONResponse:
        return error_response(status.HTTP_404_NOT_FOUND, "not_found", str(error))

    @app.exception_handler(InvalidRequestError)
    async def invalid_request(_: Request, error: InvalidRequestError) -> JSONResponse:
        return error_response(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_request", str(error))

    @app.exception_handler(DailyLimitReachedError)
    async def daily_limit_reached(_: Request, error: DailyLimitReachedError) -> JSONResponse:
        logger.warning("daily limit, request_id=%s: %s", current_request_id(), error)
        seconds = (error.resets_at - datetime.now(UTC)).total_seconds()
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ai_daily_limit",
            "The free daily allowance for the AI features is used up. They are back "
            f"from {error.resets_at:%Y-%m-%d %H:%M} UTC; everything else works as usual.",
            headers={"Retry-After": str(max(0, math.ceil(seconds)))},
        )

    @app.exception_handler(LLMUnavailableError)
    @app.exception_handler(EmbedderUnavailableError)
    async def ai_unavailable(_: Request, error: Exception) -> JSONResponse:
        # The reason (quota, timeout, no key) is for the log; the client only
        # needs to know that it should carry on without the model.
        logger.warning("model unavailable, request_id=%s: %s", current_request_id(), error)
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ai_unavailable",
            "The AI assistant is not available right now. Everything else works as usual.",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(
                # ("body", "weights", "rent") -> "weights.rent"
                field=".".join(str(part) for part in item["loc"][1:]) or str(item["loc"][0]),
                problem=item["msg"],
            )
            for item in error.errors()
        ]
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_request",
            "The request is not valid.",
            details,
        )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        code = "not_found" if error.status_code == status.HTTP_404_NOT_FOUND else "http_error"
        return error_response(error.status_code, code, str(error.detail))

    @app.exception_handler(Exception)
    async def unexpected(_: Request, error: Exception) -> JSONResponse:
        # The details go to the log, never to the client.
        logger.exception("unhandled error, request_id=%s", current_request_id(), exc_info=error)
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "Something went wrong on the server.",
        )
