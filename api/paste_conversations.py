"""Bounded temporary follow-ups, tied to the parent analysis owner and expiry.

Single worker/replica private beta only. Source text stays with PasteJobs, never in a
client-provided history. Request IDs are scoped to an analysis and bind exact payloads.
"""
from __future__ import annotations

import copy
import logging
import secrets
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from api.paste_jobs import BusyError, PasteJobs
from product.paste import PasteRequest
from product.paste_chat import MAX_TURNS, QuestionRequest

_LOG = logging.getLogger(__name__)
Runner = Callable[[PasteRequest, dict, list[dict], str], dict]


class ConversationMissing(LookupError):
    pass


class ConversationConflict(RuntimeError):
    pass


@dataclass
class _Turn:
    question_id: str
    request_id: str
    index: int
    question: str
    status: str = "processing"
    result: dict | None = None
    error_code: str | None = None

    def public(self) -> dict:
        return {"question_id": self.question_id, "request_id": self.request_id,
                "turn_index": self.index, "question": self.question,
                "status": self.status, "result": copy.deepcopy(self.result),
                "error_code": self.error_code}


@dataclass
class _Conversation:
    owner: str
    analysis_id: str
    turns: list[_Turn] = field(default_factory=list)


class FollowupJobs:
    def __init__(self, parents: PasteJobs, runner: Runner, *, max_active: int = 2,
                 owner_limit: int = 12, hourly_limit: int = 60, max_conversations: int = 64,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.parents, self.runner, self.clock = parents, runner, clock
        self.max_active, self.owner_limit, self.hourly_limit = max_active, owner_limit, hourly_limit
        self.max_conversations = max_conversations
        self._conversations: dict[tuple[str, str], _Conversation] = {}
        self._starts: deque[tuple[float, str]] = deque()
        self._lock = threading.RLock()
        self._active = 0
        self._closed = False
        self._pool = ThreadPoolExecutor(max_workers=max_active, thread_name_prefix="paste-question")
        self._stop = threading.Event()
        self._janitor = threading.Thread(target=self._sweep, name="question-expiry", daemon=True)
        self._janitor.start()

    def _parent(self, owner: str, analysis_id: str) -> tuple[PasteRequest, dict]:
        context = self.parents.context(owner, analysis_id)
        if context is None:
            raise ConversationMissing("This analysis has expired or is not available in this browser.")
        source, card = context
        if card.get("capabilities", {}).get("questions") is False:
            raise ConversationMissing("Questions are not enabled for this information card.")
        if (card.get("source_hash") != source.source_hash
                or card.get("integrity", {}).get("status") != "passed"):
            raise ConversationMissing("A checked analysis is needed before asking a question.")
        return context

    def _prune(self) -> None:
        now = self.clock()
        while self._starts and now - self._starts[0][0] >= 3600:
            self._starts.popleft()
        for key in list(self._conversations):
            if self.parents.get(*key) is None:
                del self._conversations[key]

    def _sweep(self) -> None:
        while not self._stop.wait(60):
            with self._lock:
                self._prune()

    def history(self, owner: str, analysis_id: str) -> dict:
        with self._lock:
            self._prune()
            self._parent(owner, analysis_id)
            conversation = self._conversations.get((owner, analysis_id))
            turns = conversation.turns if conversation else []
            return {"analysis_id": analysis_id, "turns": [t.public() for t in turns],
                    "next_turn_index": len(turns), "remaining": MAX_TURNS - len(turns)}

    def submit(self, owner: str, analysis_id: str, request: QuestionRequest) -> dict:
        with self._lock:
            self._prune()
            if self._closed:
                raise BusyError("Questions are temporarily unavailable.")
            source, analysis = self._parent(owner, analysis_id)
            key = (owner, analysis_id)
            conversation = self._conversations.get(key)
            turns = conversation.turns if conversation else []
            for previous in turns:
                if previous.request_id == request.request_id:
                    if previous.question != request.question or previous.index != request.turn_index:
                        raise ConversationConflict("This request already belongs to a different question.")
                    return previous.public()
            if any(t.status == "processing" for t in turns):
                raise ConversationConflict("Another question is being answered. Check the conversation first.")
            if request.turn_index != len(turns):
                raise ConversationConflict("The conversation has changed. Refresh it before asking again.")
            if len(turns) >= MAX_TURNS:
                raise BusyError("The question limit for this announcement has been reached.")
            now = self.clock()
            recent = sum(t > now - 600 and user == owner for t, user in self._starts)
            if recent >= self.owner_limit or len(self._starts) >= self.hourly_limit:
                raise BusyError("The question limit has been reached. Please try again later.")
            if self._active >= self.max_active:
                raise BusyError("All question slots are busy. Please try again shortly.")
            if conversation is None:
                if len(self._conversations) >= self.max_conversations:
                    raise BusyError("All conversation slots are busy. Please try again later.")
                conversation = _Conversation(owner, analysis_id)
                self._conversations[key] = conversation
            history = [{"question": t.question, "answer": t.result["paragraphs"]}
                       for t in turns if t.status == "complete" and t.result]
            turn = _Turn(secrets.token_urlsafe(24), request.request_id, len(turns), request.question)
            conversation.turns.append(turn)
            self._starts.append((now, owner))
            self._active += 1
            try:
                self._pool.submit(self._run, key, turn, source, analysis, history)
            except RuntimeError:
                conversation.turns.pop()
                self._starts.pop()
                self._active -= 1
                if not conversation.turns:
                    self._conversations.pop(key, None)
                raise BusyError("Questions are temporarily unavailable.") from None
            return turn.public()

    def _run(self, key: tuple[str, str], turn: _Turn, source: PasteRequest,
             analysis: dict, history: list[dict]) -> None:
        try:
            result = self.runner(source, analysis, history, turn.question)
            if not isinstance(result, dict) or result.get("source_hash") != source.source_hash:
                raise ValueError("Answer source mismatch")
        except Exception as exc:
            _LOG.warning("paste_question_failed type=%s", type(exc).__name__)
            result = None
            code = "REVIEW_REQUIRED" if type(exc).__name__ == "FollowupQualityError" else "ANSWER_UNAVAILABLE"
        else:
            code = None
        finally:
            with self._lock:
                try:
                    self._parent(*key)
                except ConversationMissing:
                    self._conversations.pop(key, None)
                    turn.result = None
                    turn.status = "failed"
                    turn.error_code = "EXPIRED"
                else:
                    turn.result = copy.deepcopy(result)
                    turn.status = "complete" if result is not None else "failed"
                    turn.error_code = code
                self._active -= 1

    def get(self, owner: str, analysis_id: str, question_id: str) -> dict:
        with self._lock:
            self._prune()
            self._parent(owner, analysis_id)
            conversation = self._conversations.get((owner, analysis_id))
            if conversation:
                for turn in conversation.turns:
                    if turn.question_id == question_id:
                        return turn.public()
            raise ConversationMissing("This question has expired or is not available in this browser.")

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            self._closed = True
        self._pool.shutdown(wait=True)
        self._janitor.join(timeout=2)
        with self._lock:
            self._conversations.clear()
            self._starts.clear()
