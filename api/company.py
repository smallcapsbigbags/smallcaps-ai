from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from database.company_sheet import CompanySheetRepository
from database.db import create_database_engine, create_session_factory, init_database
from product.company_sheet import COMPANY_SHEET_SCHEMA_VERSION, CompanySheet
from settings import Settings

RepositoryProvider = Callable[[], CompanySheetRepository]


@lru_cache(maxsize=4)
def _repository_for_url(database_url: str) -> CompanySheetRepository:
    engine = create_database_engine(database_url)
    init_database(engine)
    return CompanySheetRepository(create_session_factory(engine))


def default_repository() -> CompanySheetRepository:
    settings = Settings.from_env()
    errors, _warnings = settings.runtime_issues("web")
    if errors:
        raise RuntimeError("; ".join(errors))
    return _repository_for_url(settings.database_url)


def create_company_routes(
    repository_provider: RepositoryProvider | None = None,
) -> list[Route]:
    """Create the versioned, publication-safe Company Intelligence API."""

    provider = repository_provider or default_repository

    async def schema(_request: Request) -> Response:
        return _json(
            {
                "schema_version": COMPANY_SHEET_SCHEMA_VERSION,
                "company": CompanySheet.model_json_schema(),
            },
            cache_seconds=3600,
        )

    async def company(request: Request) -> Response:
        ticker = str(request.path_params.get("ticker") or "").strip()
        if not ticker or len(ticker) > 20:
            return _client_error(
                "INVALID_TICKER",
                "A valid company ticker is required.",
                status_code=400,
            )
        try:
            result = provider().get_company(ticker)
        except Exception as exc:  # pragma: no cover - production logging path
            return _service_error(exc)
        if result is None:
            return _client_error(
                "NOT_FOUND",
                "This company does not yet have publishable Smallcaps.ai coverage.",
                status_code=404,
            )
        return _json(result.model_dump(mode="json"), cache_seconds=60)

    return [
        Route(
            "/api/v1/schemas/company-sheet",
            schema,
            methods=["GET"],
        ),
        Route(
            "/api/v1/company/{ticker}",
            company,
            methods=["GET"],
        ),
    ]


def _headers(*, cache_seconds: int) -> dict[str, str]:
    cache = (
        "no-store"
        if cache_seconds <= 0
        else f"public, max-age={cache_seconds}, stale-while-revalidate=300"
    )
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Accept, Content-Type",
        "Cache-Control": cache,
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "X-Content-Type-Options": "nosniff",
    }


def _json(payload: Any, *, cache_seconds: int, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status_code,
        headers=_headers(cache_seconds=cache_seconds),
    )


def _client_error(code: str, message: str, *, status_code: int) -> JSONResponse:
    return _json(
        {
            "schema_version": COMPANY_SHEET_SCHEMA_VERSION,
            "error": {"code": code, "message": message},
        },
        cache_seconds=0,
        status_code=status_code,
    )


def _service_error(exc: Exception) -> JSONResponse:
    reference = uuid.uuid4().hex[:12]
    print(
        "[company-api-error] "
        + json.dumps(
            {
                "reference": reference,
                "exception": type(exc).__name__,
                "message": str(exc),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return _json(
        {
            "schema_version": COMPANY_SHEET_SCHEMA_VERSION,
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Company research is temporarily unavailable.",
                "reference": reference,
            },
        },
        cache_seconds=0,
        status_code=503,
    )
