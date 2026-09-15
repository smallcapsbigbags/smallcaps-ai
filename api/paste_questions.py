"""Private-beta follow-up endpoints. Same-origin, source-scoped and bounded."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Callable

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from api.paste import _bounded_env, _error, _response, _session, access_error, default_jobs
from api.paste_conversations import ConversationConflict, ConversationMissing, FollowupJobs
from api.paste_jobs import BusyError
from product.paste_chat import QuestionRequest
from settings import Settings


@lru_cache(maxsize=1)
def default_followups() -> FollowupJobs:
    from analyst.paste_chat import answer_question
    return FollowupJobs(default_jobs(), answer_question,
        hourly_limit=_bounded_env("PASTE_MAX_QUESTIONS_PER_HOUR", 60, 100),
        owner_limit=_bounded_env("PASTE_MAX_QUESTIONS_PER_SESSION", 12, 20))


def create_question_routes(jobs_provider: Callable[[], FollowupJobs] = default_followups,
                           settings_provider: Callable[[], Settings] = Settings.from_env) -> list[Route]:
    async def questions(request: Request) -> JSONResponse:
        settings = settings_provider()
        denied = access_error(request, settings)
        if denied is not None:
            return denied
        if os.getenv("PASTE_CHAT_ENABLED", "true").lower() not in {"1", "true", "yes"}:
            return _error("CHAT_DISABLED", "Questions are not available here yet.", 503)
        owner, _token = _session(request, settings.app_beta_password)
        analysis_id = request.path_params["analysis_id"]
        try:
            if request.method == "GET":
                if "question_id" in request.path_params:
                    return _response(jobs_provider().get(owner, analysis_id, request.path_params["question_id"]))
                return _response(jobs_provider().history(owner, analysis_id))
            origin = request.headers.get("origin")
            expected = f"{request.url.scheme}://{request.url.netloc}"
            if (origin is not None and origin != expected) or request.headers.get("x-smallcaps-action") != "ask":
                return _error("INVALID_ORIGIN", "Please ask your question from this page.", 403)
            if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                return _error("INVALID_CONTENT_TYPE", "Send the question as text in JSON.", 415)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 16_000:
                    return _error("INPUT_TOO_LARGE", "Keep your question under 2,000 characters.", 413)
            try:
                question = QuestionRequest.model_validate(json.loads(body))
            except (ValueError, UnicodeDecodeError, ValidationError):
                return _error("INVALID_INPUT", "Ask a question between 3 and 2,000 characters.", 422)
            # Ownership and parent readiness are verified even when a credential is missing.
            jobs_provider().history(owner, analysis_id)
            if not settings.openai_api_key:
                return _error("ANSWER_UNAVAILABLE", "Questions are temporarily unavailable. Your question is still here.", 503)
            payload = jobs_provider().submit(owner, analysis_id, question)
            return _response(payload, 202 if payload["status"] == "processing" else 200)
        except ConversationMissing:
            return _error("NOT_FOUND", "This analysis has expired or is not available in this browser. Paste it again to continue.", 404)
        except ConversationConflict as exc:
            return _error("CONVERSATION_CHANGED", str(exc), 409)
        except BusyError as exc:
            response = _error("QUESTIONS_BUSY", str(exc), 429)
            response.headers["Retry-After"] = "60"
            return response

    return [
        Route("/api/v1/analyse/{analysis_id}/questions", questions, methods=["GET", "POST"]),
        Route("/api/v1/analyse/{analysis_id}/questions/{question_id}", questions, methods=["GET"]),
    ]
