from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time
from functools import lru_cache
from typing import Any, Callable
from zoneinfo import ZoneInfo

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from database.db import create_database_engine, create_session_factory, init_database
from database.newsroom import NewsroomRepository
from product.daily_editor import resolve_editor_cutoff
from product.newsroom import NEWSROOM_SCHEMA_VERSION, NEWSROOM_VERSION, NewsroomEdition
from settings import Settings

LONDON = ZoneInfo("Europe/London")
RepositoryProvider = Callable[[], NewsroomRepository]


@lru_cache(maxsize=4)
def _repository_for_url(database_url: str) -> NewsroomRepository:
    engine = create_database_engine(database_url)
    init_database(engine)
    return NewsroomRepository(create_session_factory(engine))


def default_repository() -> NewsroomRepository:
    settings = Settings.from_env()
    errors, _warnings = settings.runtime_issues("web")
    if errors:
        raise RuntimeError("; ".join(errors))
    return _repository_for_url(settings.database_url)


def create_newsroom_routes(
    repository_provider: RepositoryProvider | None = None,
) -> list[Route]:
    provider = repository_provider or default_repository

    async def schema(_request: Request) -> Response:
        return _json(
            {
                "schema_version": NEWSROOM_SCHEMA_VERSION,
                "newsroom_version": NEWSROOM_VERSION,
                "edition": NewsroomEdition.model_json_schema(),
                "house_rule": "Journalistic in selection. Analytical in judgement. Relentless about the facts.",
            },
            cache_seconds=3600,
        )

    async def newsroom(request: Request) -> Response:
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

    return [
        Route("/api/v1/schemas/aim-daily-newsroom", schema, methods=["GET"]),
        Route("/api/v1/aim-daily/newsroom", newsroom, methods=["GET"]),
    ]


def _parse_query(request: Request) -> tuple[date, str | None, time | None]:
    params = request.query_params
    day_value = str(params.get("date") or "").strip()
    if day_value:
        try:
            day = date.fromisoformat(day_value)
        except ValueError as exc:
            raise ValueError("date must use YYYY-MM-DD") from exc
    else:
        day = datetime.now(LONDON).date()

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

    resolve_editor_cutoff(edition_state=state_value or None, cutoff=cutoff)
    return day, state_value or None, cutoff


def _headers(*, cache_seconds: int) -> dict[str, str]:
    cache = "no-store" if cache_seconds <= 0 else f"public, max-age={cache_seconds}, stale-while-revalidate=300"
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Accept, Content-Type",
        "Cache-Control": cache,
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "X-Content-Type-Options": "nosniff",
    }


def _json(payload: Any, *, cache_seconds: int, status_code: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status_code, headers=_headers(cache_seconds=cache_seconds))


def _client_error(code: str, message: str, *, status_code: int) -> JSONResponse:
    return _json(
        {
            "schema_version": NEWSROOM_SCHEMA_VERSION,
            "error": {"code": code, "message": message},
        },
        cache_seconds=0,
        status_code=status_code,
    )


def _service_error(exc: Exception) -> JSONResponse:
    reference = uuid.uuid4().hex[:12]
    print(
        "[newsroom-api-error] "
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
            "schema_version": NEWSROOM_SCHEMA_VERSION,
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "AIM Daily newsroom data is temporarily unavailable.",
                "reference": reference,
            },
        },
        cache_seconds=0,
        status_code=503,
    )
