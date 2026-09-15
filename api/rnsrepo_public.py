"""Same-origin anonymous card handlers; retained analyst/chat APIs stay protected."""
from __future__ import annotations
import asyncio
import json
import os
from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.paste_jobs import BusyError
from product.paste import PasteRequest
from rnsrepo.public_access import (COOKIE, COOKIE_PATH, SESSION_SECONDS, PublicAccessError,
                                   PublicConfig, budget, build_fingerprint)


def response(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status, headers={
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'"})


def error(exc: PublicAccessError) -> JSONResponse:
    result = response({'error': {'code': exc.code, 'message': exc.message}}, exc.status)
    if exc.status in (429, 503):
        result.headers['Retry-After'] = str(exc.retry_after)
    return result


class PublicCards:
    def __init__(self, jobs_provider: Callable, settings_provider: Callable, budget_provider: Callable = budget):
        self.jobs_provider, self.settings_provider, self.budget_provider = jobs_provider, settings_provider, budget_provider

    async def prepare(self, request: Request) -> JSONResponse:
        try:
            cfg = PublicConfig.from_env()
            cfg.check_origin(request)
            if request.headers.get('x-smallcaps-action') != 'prepare':
                raise PublicAccessError('INVALID_ORIGIN', 'Please open the demo in your browser.', 403)
            _owner, token, csrf = cfg.prepare_session(request)
            result = response({'ready': True, 'max_characters': 120000, 'csrf_token': csrf, 'access': 'anonymous', 'build': build_fingerprint()})
            result.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                              secure=cfg.origin.startswith('https://'), samesite='strict', path=COOKIE_PATH)
            return result
        except PublicAccessError as exc:
            return error(exc)

    async def analyse(self, request: Request) -> JSONResponse:
        try:
            if os.getenv('PASTE_ANALYSIS_ENABLED', 'true').lower() not in {'1', 'true', 'yes'}:
                raise PublicAccessError('ANALYSIS_DISABLED', 'The demo is paused. Your text is still here.')
            cfg = PublicConfig.from_env()
            owner = cfg.require_owner(request, mutation=True)
            network = cfg.network(request)
            if request.headers.get('x-smallcaps-action') != 'analyse':
                raise PublicAccessError('INVALID_ORIGIN', 'Please submit the announcement from this page.', 403)
            if request.headers.get('content-type', '').split(';')[0].lower() != 'application/json':
                raise PublicAccessError('INVALID_CONTENT_TYPE', 'Paste the announcement as plain text.', 415)
            if not self.settings_provider().openai_api_key:
                raise PublicAccessError('CARD_CONFIGURATION', 'The summary service is not configured. Your text is still here.')
            body = bytearray()
            # Do not hold a worker slot while an anonymous client slowly uploads a body.
            try:
                async with asyncio.timeout(15):
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > 520000:
                            raise PublicAccessError('INPUT_TOO_LONG', 'The limit is 120,000 characters.', 413)
            except TimeoutError:
                raise PublicAccessError('INPUT_TIMEOUT', 'The upload took too long. Your text is still here.', 408) from None
            try:
                source = PasteRequest.model_validate(json.loads(body))
            except (ValueError, UnicodeDecodeError, ValidationError):
                raise PublicAccessError('INVALID_INPUT', 'Paste one announcement, including its header, between 120 and 120,000 characters.', 422) from None
            def submit():
                # Existing job cache is checked BEFORE this callback, so a repeated
                # click/lost-response recovery never spends another reserved slot.
                return self.jobs_provider().submit(owner, source,
                    admit=lambda: self.budget_provider().reserve(owner, network))
            import anyio
            payload = await anyio.to_thread.run_sync(submit)
            return response(payload, 202 if payload['status'] == 'processing' else 200)
        except PublicAccessError as exc:
            return error(exc)
        except BusyError:
            return error(PublicAccessError('ANALYSIS_BUSY', 'The demo is busy. Your text is still here; try again shortly.', 429))
        except SQLAlchemyError:
            # Fail closed: never fall back to an in-memory allowance on storage failure.
            return error(PublicAccessError('DEMO_BUDGET_UNAVAILABLE', 'The demo is temporarily unavailable. Your text is still here.'))

    async def status(self, request: Request) -> JSONResponse:
        try:
            cfg = PublicConfig.from_env()
            cfg.check_origin(request)
            owner = cfg.require_owner(request)
            payload = self.jobs_provider().get(owner, request.path_params['analysis_id'])
            if payload is None:
                return error(PublicAccessError('NOT_FOUND', 'This temporary card has expired or belongs to another browser. Your pasted text is still here.', 404))
            return response(payload)
        except PublicAccessError as exc:
            return error(exc)
