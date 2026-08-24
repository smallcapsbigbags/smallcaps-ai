from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache
from pathlib import Path
from typing import Final

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from settings import Settings

_COOKIE_NAME: Final = "smallcaps_beta"
_COOKIE_MAX_AGE: Final = 60 * 60 * 24 * 30
_FRONTEND_ROOT = Path(__file__).resolve().parents[1] / "frontend"


@lru_cache(maxsize=4)
def _serializer(secret: str) -> URLSafeTimedSerializer:
    digest = hashlib.sha256(f"smallcaps-ai-beta:{secret}".encode("utf-8")).hexdigest()
    return URLSafeTimedSerializer(digest, salt="smallcaps-ai-monitoring-sheet")


def _token(secret: str) -> str:
    return _serializer(secret).dumps({"access": "monitoring-sheet"})


def _valid_token(value: str, secret: str) -> bool:
    if not value or not secret:
        return False
    try:
        payload = _serializer(secret).loads(value, max_age=_COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return isinstance(payload, dict) and payload.get("access") == "monitoring-sheet"


def _security_headers(*, cache: str = "no-store") -> dict[str, str]:
    return {
        "Cache-Control": cache,
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "base-uri 'none'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }


def _file(path: Path, *, media_type: str = "text/html") -> FileResponse:
    return FileResponse(path, media_type=media_type, headers=_security_headers())


def _access_html(*, failed: bool = False) -> str:
    source = (_FRONTEND_ROOT / "access.html").read_text(encoding="utf-8")
    message = (
        '<p class="access-error" role="alert">That access code was not recognised.</p>'
        if failed
        else ""
    )
    return source.replace("{{ACCESS_ERROR}}", message)


def create_frontend_routes() -> list[Route]:
    """Serve the monitoring sheet and a server-validated private-beta entrance."""

    async def home(request: Request) -> Response:
        settings = Settings.from_env()
        if settings.private_beta_mode and not _valid_token(
            request.cookies.get(_COOKIE_NAME, ""), settings.app_beta_password
        ):
            return HTMLResponse(_access_html(), headers=_security_headers())
        return _file(_FRONTEND_ROOT / "index.html")

    async def access(request: Request) -> Response:
        settings = Settings.from_env()
        if not settings.private_beta_mode:
            return RedirectResponse("/", status_code=303)
        form = await request.form()
        supplied = str(form.get("access_code") or "")
        expected = settings.app_beta_password
        if not expected or not hmac.compare_digest(supplied, expected):
            return HTMLResponse(
                _access_html(failed=True),
                status_code=401,
                headers=_security_headers(),
            )

        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            _COOKIE_NAME,
            _token(expected),
            max_age=_COOKIE_MAX_AGE,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
            path="/",
        )
        for key, value in _security_headers().items():
            response.headers[key] = value
        return response

    async def logout(_request: Request) -> Response:
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(_COOKIE_NAME, path="/")
        for key, value in _security_headers().items():
            response.headers[key] = value
        return response

    async def favicon(_request: Request) -> Response:
        return _file(
            _FRONTEND_ROOT / "assets" / "favicon.svg",
            media_type="image/svg+xml",
        )

    return [
        Route("/", home, methods=["GET"]),
        Route("/access", access, methods=["POST"]),
        Route("/logout", logout, methods=["POST"]),
        Route("/favicon.svg", favicon, methods=["GET"]),
    ]
