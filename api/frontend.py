from __future__ import annotations

import hashlib
import hmac
import html
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
_ASSET_VERSION_PLACEHOLDER: Final = "{{ASSET_VERSION}}"


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


@lru_cache(maxsize=1)
def _asset_version() -> str:
    """Return a deterministic fingerprint for every customer-facing asset.

    HTML responses are never cached, so embedding this value in stylesheet and
    script URLs forces a browser to fetch the exact asset set shipped with the
    current deployment. This prevents an older cached research.js or daily.js
    from running against a newer DOM contract.
    """

    digest = hashlib.sha256()
    asset_root = _FRONTEND_ROOT / "assets"
    for path in sorted(asset_root.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:12]


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
        "Cross-Origin-Opener-Policy": "same-origin",
        "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }


def _file(path: Path, *, media_type: str = "text/html") -> FileResponse:
    return FileResponse(path, media_type=media_type, headers=_security_headers())


def _html_file(path: Path) -> HTMLResponse:
    source = path.read_text(encoding="utf-8").replace(
        _ASSET_VERSION_PLACEHOLDER,
        _asset_version(),
    )
    return HTMLResponse(source, headers=_security_headers())


def _safe_next(value: object) -> str:
    path = str(value or "/").strip()
    if (
        not path.startswith("/")
        or path.startswith("//")
        or any(character in path for character in ("\r", "\n", "\x00"))
    ):
        return "/"
    return path


def _request_target(request: Request) -> str:
    query = request.url.query
    return _safe_next(f"{request.url.path}?{query}" if query else request.url.path)


def _access_html(*, failed: bool = False, next_path: str = "/") -> str:
    source = (_FRONTEND_ROOT / "access.html").read_text(encoding="utf-8")
    message = (
        '<p class="access-error" role="alert">That access code was not recognised.</p>'
        if failed
        else ""
    )
    return (
        source.replace("{{ACCESS_ERROR}}", message)
        .replace("{{ACCESS_NEXT}}", html.escape(_safe_next(next_path), quote=True))
        .replace(_ASSET_VERSION_PLACEHOLDER, _asset_version())
    )


def _authorised(request: Request, settings: Settings) -> bool:
    return not settings.private_beta_mode or _valid_token(
        request.cookies.get(_COOKIE_NAME, ""), settings.app_beta_password
    )


def _protected_file(request: Request, filename: str) -> Response:
    settings = Settings.from_env()
    if not _authorised(request, settings):
        return HTMLResponse(
            _access_html(next_path=_request_target(request)),
            headers=_security_headers(),
        )
    return _html_file(_FRONTEND_ROOT / filename)


def create_frontend_routes() -> list[Route]:
    """Serve The AIM Daily, Company News, Company Intelligence and beta entrance."""

    async def home(request: Request) -> Response:
        # Legacy company links may still deep-link to /?date=...&open=SOURCE_ID.
        # Keep those stable while making the plain root URL The AIM Daily.
        filename = "index.html" if request.query_params.get("open") else "daily.html"
        return _protected_file(request, filename)

    async def rns(request: Request) -> Response:
        return _protected_file(request, "index.html")

    async def rns_slash(request: Request) -> Response:
        query = request.url.query
        target = f"/rns?{query}" if query else "/rns"
        return RedirectResponse(target, status_code=308, headers=_security_headers())

    async def company(request: Request) -> Response:
        return _protected_file(request, "company.html")

    async def access(request: Request) -> Response:
        settings = Settings.from_env()
        form = await request.form()
        next_path = _safe_next(form.get("next"))
        if not settings.private_beta_mode:
            return RedirectResponse(next_path, status_code=303)
        supplied = str(form.get("access_code") or "")
        expected = settings.app_beta_password
        if not expected or not hmac.compare_digest(supplied, expected):
            return HTMLResponse(
                _access_html(failed=True, next_path=next_path),
                status_code=401,
                headers=_security_headers(),
            )

        response = RedirectResponse(next_path, status_code=303)
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
        Route("/rns", rns, methods=["GET"]),
        Route("/rns/", rns_slash, methods=["GET"]),
        Route("/company/{ticker}", company, methods=["GET"]),
        Route("/access", access, methods=["POST"]),
        Route("/logout", logout, methods=["POST"]),
        Route("/favicon.svg", favicon, methods=["GET"]),
    ]
