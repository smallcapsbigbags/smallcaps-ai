from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable
from datetime import date, datetime
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from database.db import create_database_engine, create_session_factory, init_database
from database.monitoring import MonitoringSheetQuery, MonitoringSheetRepository
from product.monitoring import (
    MONITORING_SCHEMA_VERSION,
    MonitoringSheetDetail,
    MonitoringSheetPage,
)
from settings import Settings

LONDON = ZoneInfo("Europe/London")
RepositoryProvider = Callable[[], MonitoringSheetRepository]


@lru_cache(maxsize=4)
def _repository_for_url(database_url: str) -> MonitoringSheetRepository:
    engine = create_database_engine(database_url)
    init_database(engine)
    return MonitoringSheetRepository(create_session_factory(engine))


def default_repository() -> MonitoringSheetRepository:
    settings = Settings.from_env()
    errors, _warnings = settings.runtime_issues("web")
    if errors:
        raise RuntimeError("; ".join(errors))
    return _repository_for_url(settings.database_url)


def create_monitoring_routes(
    repository_provider: RepositoryProvider | None = None,
) -> list[Route]:
    """Create the versioned monitoring API routes.

    Dependency injection keeps endpoint tests independent from the Streamlit runtime
    while production uses the same PostgreSQL database and publication gate as the UI.
    """

    provider = repository_provider or default_repository

    async def health(_request: Request) -> Response:
        try:
            payload = provider().health()
        except Exception as exc:  # pragma: no cover - exercised by production logging
            return _service_error(exc)
        return _json(payload, cache_seconds=0)

    async def schema(_request: Request) -> Response:
        payload = {
            "schema_version": MONITORING_SCHEMA_VERSION,
            "list": MonitoringSheetPage.model_json_schema(),
            "detail": MonitoringSheetDetail.model_json_schema(),
        }
        return _json(payload, cache_seconds=3600)

    async def list_monitoring(request: Request) -> Response:
        try:
            query = _parse_query(request)
            page = provider().list_rows(query)
        except ValueError as exc:
            return _client_error("INVALID_QUERY", str(exc), status_code=400)
        except Exception as exc:  # pragma: no cover - exercised by production logging
            return _service_error(exc)
        return _json(page.model_dump(mode="json"), cache_seconds=60)

    async def monitoring_detail(request: Request) -> Response:
        source_id = str(request.path_params.get("source_id") or "").strip()
        if not source_id:
            return _client_error(
                "INVALID_SOURCE_ID",
                "source_id is required",
                status_code=400,
            )
        try:
            detail = provider().get_detail(source_id)
        except Exception as exc:  # pragma: no cover - exercised by production logging
            return _service_error(exc)
        if detail is None:
            return _client_error(
                "NOT_FOUND",
                "No publishable monitoring record matches this source_id.",
                status_code=404,
            )
        return _json(detail.model_dump(mode="json"), cache_seconds=60)

    async def options(_request: Request) -> Response:
        return Response(status_code=204, headers=_headers(cache_seconds=0))

    return [
        Route("/api/v1/health", health, methods=["GET"]),
        Route(
            "/api/v1/schemas/monitoring-sheet",
            schema,
            methods=["GET"],
        ),
        Route("/api/v1/monitoring", list_monitoring, methods=["GET"]),
        Route(
            "/api/v1/monitoring/{source_id}",
            monitoring_detail,
            methods=["GET"],
        ),
        Route("/api/v1/{path:path}", options, methods=["OPTIONS"]),
    ]


def _parse_query(request: Request) -> MonitoringSheetQuery:
    params = request.query_params
    today = datetime.now(LONDON).date()
    exact_day = params.get("date", "").strip()
    if exact_day and (params.get("date_from") or params.get("date_to")):
        raise ValueError("date cannot be combined with date_from or date_to")

    if exact_day:
        date_from = date_to = _parse_date("date", exact_day)
    else:
        date_from = (
            _parse_date("date_from", params.get("date_from"))
            if params.get("date_from")
            else today
        )
        date_to = (
            _parse_date("date_to", params.get("date_to"))
            if params.get("date_to")
            else date_from
        )

    tickers = _multi_values(params.getlist("ticker"), params.get("tickers"))
    signals = _multi_values(params.getlist("signal"), params.get("signals"))
    outlooks = _multi_values(params.getlist("outlook"), params.get("outlooks"))
    sort = str(params.get("sort") or "latest").strip().lower()
    search = str(params.get("search") or "")
    limit = _parse_int("limit", params.get("limit"), default=100)
    offset = _parse_int("offset", params.get("offset"), default=0)

    return MonitoringSheetQuery(
        date_from=date_from,
        date_to=date_to,
        tickers=tuple(tickers),
        search=search,
        signals=tuple(signals),  # type: ignore[arg-type]
        outlooks=tuple(outlooks),  # type: ignore[arg-type]
        sort=sort,  # type: ignore[arg-type]
        limit=limit,
        offset=offset,
    )


def _parse_date(name: str, value: str | None) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ValueError(f"{name} must use YYYY-MM-DD") from exc


def _parse_int(name: str, value: str | None, *, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _multi_values(repeated: Iterable[str], comma_value: str | None) -> list[str]:
    output: list[str] = []
    for value in [*repeated, *str(comma_value or "").split(",")]:
        clean = " ".join(str(value or "").strip().split())
        if clean and clean not in output:
            output.append(clean)
    return output


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
            "schema_version": MONITORING_SCHEMA_VERSION,
            "error": {"code": code, "message": message},
        },
        cache_seconds=0,
        status_code=status_code,
    )


def _service_error(exc: Exception) -> JSONResponse:
    reference = uuid.uuid4().hex[:12]
    print(
        "[monitoring-api-error] "
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
            "schema_version": MONITORING_SCHEMA_VERSION,
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "Monitoring data is temporarily unavailable.",
                "reference": reference,
            },
        },
        cache_seconds=0,
        status_code=503,
    )
