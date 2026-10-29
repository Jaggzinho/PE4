from __future__ import annotations

import re

import duckdb
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def _code_for_status(status_code: int) -> str:
    names = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        413: "payload_too_large",
        422: "validation_error",
        501: "not_implemented",
        503: "service_unavailable",
    }
    return names.get(status_code, f"http_{status_code}")


def _message(detail: object, status_code: int) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    return re.sub(r"_+", " ", _code_for_status(status_code)).capitalize()


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(duckdb.ConstraintException)
    async def database_constraint_error(_request: Request, _exc: duckdb.ConstraintException) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "code": "conflict",
                "message": "The record is referenced or conflicts with existing data",
                "detail": "The requested change violates a database constraint",
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        message = _message(exc.detail, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder(
                {"code": _code_for_status(exc.status_code), "message": message, "detail": exc.detail}
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "detail": exc.errors(),
                }
            ),
        )
