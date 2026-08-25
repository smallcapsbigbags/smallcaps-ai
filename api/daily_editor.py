from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import date, datetime, time
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from database.daily_editor import DailyEditorRepository, canonical_cutoffs
from database.db import create_database_engine, create_session_factory, init_database
from product.daily_editor import (
    DAILY_EDITOR_SCHEMA_VERSION,
    DailyEditorPage,
    DailyEditorTimeline,
    resolve_editor_cutoff,
)
from settings import Settings

LONDON = ZoneInfo("Europe/London")
RepositoryProvider = Callable[[], DailyEditorRepository]


@lru_cache(maxsize=4)
def _repository_for_url(database_url: str) -> DailyEditorRepository:
    engine = create_database_engine(database_url)
    init_database(engine)
    return DailyEditorRepository(create_session_factory(engine))


def default_repository() -> DailyEditorRepository:
    settings = Settings.from_env()
    errors, _warnings = settings.runtime_issues("web")
    if errors:
        raise RuntimeError("; ".join(errors))
    return _repository_for_url(settings.database_url)


def create_daily_editor_routes(
    repository_provider: RepositoryProvider | None = None,
) -> list[Route]:
    provider = repository_provider or default_repository

    async def schema(_request: Request) -> Response:
        return _json(
            {
                "schema_version": DAILY_EDITOR_SCHEMA_VERSION,
                "canonical_cutoffs": canonical_cutoffs(),
                "edition": DailyEditorPage.model_json_schema(),
                "timeline": DailyEditorTimeline.model_json_schema(),
            },
            cache_seconds=3600,
        )

    async def aim_daily(request: Request) -> Response:
        try:
            day, edition_state, cutoff = _parse_query(request)
            edition = provider().get_edition(
                day,
                edition_state=edition_state,
                cutoff=cutoff,
            )
        except ValueError as exc:
            return _client_error("INVALID_QUERY", str(exc), status_code=400)
        except Exception as exc:  # pragma: no cover - production logging path
            return _service_error(exc)
        return _json(edition.model_dump(mode="json"), cache_seconds=60)

    async def timeline(request: Request) -> Response:
        try:
            day = _parse_day(request)
            if request.query_params.get("state") or request.query_params.get("edition_state") or request.query_params.get("cutoff"):
                raise ValueError("timeline accepts date only")
            payload = provider().get_timeline(day)
        except ValueError as exc:
            return _client_error("INVALID_QUERY", str(exc), status_code=400)
        except Exception as exc:  # pragma: no cover - production logging path
            return _service_error(exc)
        return _json(payload.model_dump(mode="json"), cache_seconds=60)

    return [
        Route(
            "/api/v1/schemas/aim-daily-editor",
            schema,
            methods=["GET"],
        ),
        Route("/api/v1/aim-daily/timeline", timeline, methods=["GET"]),
        Route("/api/v1/aim-daily", aim_daily, methods=["GET"]),
    ]


def _parse_query(request: Request) -> tuple[date, str | None, time | None]:
    day = _parse_day(request)
    params = request.query_params
    state_value = str(params.get("state") or params.get("edition_state") or "").strip().lower()
    cutoff_value = str(params.get("cutoff") or "").strip()
    if state_value and cutoff_value:
        raise ValueError("edition_state cannot be combined with cutoff")

    cutoff: time | None = None
    if cutoff_value:
        try:
            cutoff = time.fromisoformat(cutoff_value)
        except ValueError as exc:
            raise ValueError("cutoff must use HH:MM") from exc
        if cutoff.second or cutoff.microsecond:
            raise ValueError("cutoff must use HH:MM")

    resolve_editor_cutoff(
        edition_state=state_value or None,
        cutoff=cutoff,
    )
    return day, state_value or None, cutoff


def _parse_day(request: Request) -> date:
    day_value = str(request.query_params.get("date") or "").strip()
    if not day_value:
        return datetime.now(LONDON).date()
    try:
        return date.fromisoformat(day_value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc


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
            "schema_version": DAILY_EDITOR_SCHEMA_VERSION,
            "error": {"code": code, "message": message},
        },
        cache_seconds=0,
        status_code=status_code,
    )


def _service_error(exc: Exception) -> JSONResponse:
    reference = uuid.uuid4().hex[:12]
    print(
        "[daily-editor-api-error] "
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
            "schema_version": DAILY_EDITOR_SCHEMA_VERSION,
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "AIM Daily data is temporarily unavailable.",
                "reference": reference,
            },
        cache_seconds=0,
        status_code=503,
    )
