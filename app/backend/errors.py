from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail


def _error_body(code: str, message: str, request_id: str | None, detail: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if detail is not None:
        payload["error"]["detail"] = detail
    if request_id:
        payload["error"]["request_id"] = request_id
    return payload


def _status_code_to_error_code(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "UPSTREAM_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, f"HTTP_{status_code}")


def register_error_handling(app: FastAPI, logger):
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, request_id, detail=exc.detail),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "VALIDATION_ERROR",
                "Request validation failed.",
                request_id,
                detail=exc.errors(),
            ),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", None)

        # Allow already-normalized payloads to pass through.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            payload = exc.detail
            if request_id and isinstance(payload.get("error"), dict) and not payload["error"].get("request_id"):
                payload["error"]["request_id"] = request_id
            return JSONResponse(
                status_code=exc.status_code,
                content=payload,
                headers={"X-Request-ID": request_id} if request_id else None,
            )

        code = _status_code_to_error_code(exc.status_code)
        detail = None
        message = "Request failed."
        if isinstance(exc.detail, dict):
            code = str(exc.detail.get("code") or code)
            message = str(exc.detail.get("message") or exc.detail.get("detail") or message)
            detail = exc.detail.get("detail")
        elif exc.detail:
            message = str(exc.detail)

        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, message, request_id, detail=detail),
            headers={"X-Request-ID": request_id} if request_id else None,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled API exception [request_id=%s]", request_id)
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "INTERNAL_ERROR",
                "Unexpected internal error.",
                request_id,
            ),
            headers={"X-Request-ID": request_id} if request_id else None,
        )
