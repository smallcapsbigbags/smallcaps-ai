"""Authenticated, source-scoped analysis API. No shared history or source retrieval."""
from __future__ import annotations

import json
import os
import secrets
from functools import lru_cache
from typing import Callable

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from api.frontend import _COOKIE_NAME, _valid_token
from api.paste_jobs import BusyError, PasteJobs
from product.paste import PasteRequest
from settings import Settings

_SESSION_COOKIE = "smallcaps_paste_session"
_MAX_BODY_BYTES = 520_000


def _response(payload: dict[str, object], status: int = 200) -> JSONResponse:
    return JSONResponse(payload, status_code=status, headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    })


def _error(code: str, message: str, status: int) -> JSONResponse:
    return _response({"error": {"code": code, "message": message}}, status)


def _session(request: Request, secret: str) -> tuple[str, str]:
    signer = URLSafeTimedSerializer(secret, salt="smallcaps-paste-owner-v1")
    token = request.cookies.get(_SESSION_COOKIE, "")
    if token:
        try:
            owner = signer.loads(token, max_age=3600)
            if isinstance(owner, str) and len(owner) == 43:
                return owner, token
        except (BadSignature, SignatureExpired):
            pass
    owner = secrets.token_urlsafe(32)
    return owner, signer.dumps(owner)


def _bounded_env(name: str, default: int, maximum: int) -> int:
    try:
        return min(maximum, max(1, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


@lru_cache(maxsize=1)
def default_jobs() -> PasteJobs:
    # Lazy construction: opening a page or polling does not instantiate the model.
    from analyst.paste import analyse_paste
    return PasteJobs(
        analyse_paste,
        hourly_limit=_bounded_env("PASTE_MAX_JOBS_PER_HOUR", 30, 100),
        owner_limit=_bounded_env("PASTE_MAX_JOBS_PER_SESSION", 6, 20),
    )


def access_error(request: Request, settings: Settings) -> JSONResponse | None:
    enabled = os.getenv("PASTE_ANALYSIS_ENABLED", "true").lower() in {"1", "true", "yes"}
    # A paid public anonymous endpoint is deliberately NOT enabled by turning beta off.
    if not enabled or not settings.private_beta_mode or not settings.app_beta_password:
        return _error("ANALYSIS_DISABLED", "Analysis is not available here yet.", 503)
    if not _valid_token(request.cookies.get(_COOKIE_NAME, ""), settings.app_beta_password):
        return _error("AUTH_REQUIRED", "Please sign in again to analyse this announcement.", 401)
    return None


def create_paste_routes(
    jobs_provider: Callable[[], PasteJobs] = default_jobs,
    settings_provider: Callable[[], Settings] = Settings.from_env,
) -> list[Route]:
    async def prepare(request: Request) -> JSONResponse:
        settings = settings_provider()
        denied = access_error(request, settings)
        if denied is not None:
            return denied
        _owner, token = _session(request, settings.app_beta_password)
        response = _response({"ready": True, "max_characters": 120_000})
        response.set_cookie(_SESSION_COOKIE, token, max_age=3600, httponly=True,
                            secure=request.url.scheme == "https", samesite="strict", path="/api/v1/analyse")
        return response

    async def analyse(request: Request) -> JSONResponse:
        settings = settings_provider()
        denied = access_error(request, settings)
        if denied is not None:
            return denied
        origin = request.headers.get("origin")
        expected_origin = f"{request.url.scheme}://{request.url.netloc}"
        if (origin is not None and origin != expected_origin) or request.headers.get("x-smallcaps-action") != "analyse":
            return _error("INVALID_ORIGIN", "Please submit the announcement from this page.", 403)
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            return _error("INVALID_CONTENT_TYPE", "Send the announcement as plain text in JSON.", 415)
        if not settings.openai_api_key:
            return _error("ANALYSIS_UNAVAILABLE", "Analysis is temporarily unavailable. Please try again later.", 503)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > _MAX_BODY_BYTES:
                return _error("INPUT_TOO_LONG", "This announcement is too long. The limit is 120,000 characters.", 413)
        try:
            source = PasteRequest.model_validate(json.loads(body))
        except (ValueError, UnicodeDecodeError, ValidationError):
            return _error("INVALID_INPUT", "Paste one complete announcement as text, between 120 and 120,000 characters. Include its header, not a link or page HTML.", 422)
        owner, token = _session(request, settings.app_beta_password)
        try:
            payload = jobs_provider().submit(owner, source)
        except BusyError as exc:
            response = _error("ANALYSIS_BUSY", str(exc), 429)
            response.headers["Retry-After"] = "60"
            return response
        response = _response(payload, 202 if payload["status"] == "processing" else 200)
        response.set_cookie(_SESSION_COOKIE, token, max_age=3600, httponly=True,
                            secure=request.url.scheme == "https", samesite="strict", path="/api/v1/analyse")
        return response

    async def status(request: Request) -> JSONResponse:
        settings = settings_provider()
        denied = access_error(request, settings)
        if denied is not None:
            return denied
        owner, _token = _session(request, settings.app_beta_password)
        payload = jobs_provider().get(owner, request.path_params["analysis_id"])
        if payload is None:
            return _error("NOT_FOUND", "This analysis has expired or is not available in this browser.", 404)
        return _response(payload)

    return [
        Route("/api/v1/analyse", prepare, methods=["GET"]),
        Route("/api/v1/analyse", analyse, methods=["POST"]),
        Route("/api/v1/analyse/{analysis_id}", status, methods=["GET"]),
    ]
