"""Bounded in-process jobs for a single-worker private beta; not a durable queue."""
from __future__ import annotations

import logging
import copy
import secrets
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from product.paste import PasteRequest
from rnsrepo.schema import CardError

_LOG = logging.getLogger(__name__)
Runner = Callable[[PasteRequest], dict[str, object]]


class BusyError(RuntimeError):
    pass


@dataclass
class _Job:
    id: str
    owner: str
    source_hash: str
    created: float
    status: str = "processing"
    result: dict[str, object] | None = None
    error_code: str | None = None
    finished: float | None = None
    source: PasteRequest | None = None  # private; never part of public()

    def public(self) -> dict[str, object]:
        return {"analysis_id": self.id, "status": self.status,
                "result": self.result, "error_code": self.error_code}


class PasteJobs:
    def __init__(
        self, runner: Runner, *, max_active: int = 2, max_jobs: int = 64,
        owner_limit: int = 6, hourly_limit: int = 30, ttl: float = 1800,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.runner, self.clock, self.ttl = runner, clock, ttl
        self.max_active, self.max_jobs = max_active, max_jobs
        self.owner_limit, self.hourly_limit = owner_limit, hourly_limit
        self._lock = threading.RLock()
        self._jobs: dict[str, _Job] = {}
        self._starts: deque[tuple[float, str]] = deque()
        self._active = 0
        self._closed = False
        self._pool = ThreadPoolExecutor(max_workers=max_active, thread_name_prefix="paste-analyst")
        self._stop = threading.Event()
        self._janitor = threading.Thread(target=self._sweep, name="paste-expiry", daemon=True)
        self._janitor.start()

    def _prune(self) -> None:
        now = self.clock()
        for key, job in list(self._jobs.items()):
            if job.finished is not None and now - job.finished >= self.ttl:
                del self._jobs[key]
        while self._starts and now - self._starts[0][0] >= 3600:
            self._starts.popleft()

    def _sweep(self) -> None:
        while not self._stop.wait(60):
            with self._lock:
                self._prune()

    def submit(self, owner: str, source: PasteRequest) -> dict[str, object]:
        with self._lock:
            self._prune()
            if self._closed:
                raise BusyError("Analysis is temporarily unavailable.")
            # Repeated clicks and lost-response retries never start a second model job.
            for job in list(self._jobs.values()):
                if job.owner == owner and job.source_hash == source.source_hash:
                    if (job.status == "failed" and job.error_code != "REVIEW_REQUIRED"
                            and job.finished is not None and self.clock() - job.finished >= 60):
                        del self._jobs[job.id]
                        break
                    return job.public()
            now = self.clock()
            owner_recent = sum(t > now - 600 and user == owner for t, user in self._starts)
            if owner_recent >= self.owner_limit or len(self._starts) >= self.hourly_limit:
                raise BusyError("The analysis limit has been reached. Please try again later.")
            if self._active >= self.max_active or len(self._jobs) >= self.max_jobs:
                raise BusyError("All analysis slots are busy. Please try again shortly.")
            job = _Job(secrets.token_urlsafe(24), owner, source.source_hash, now)
            self._jobs[job.id] = job
            self._starts.append((now, owner))
            self._active += 1
            try:
                self._pool.submit(self._run, job.id, source)
            except RuntimeError:
                self._active -= 1
                self._starts.pop()
                del self._jobs[job.id]
                raise BusyError("Analysis is temporarily unavailable.") from None
            return job.public()

    def _run(self, job_id: str, source: PasteRequest) -> None:
        try:
            result = self.runner(source)
        except Exception as exc:
            # Never log the exception message: provider errors can contain source text.
            _LOG.warning("paste_analysis_failed job=%s type=%s", job_id, type(exc).__name__)
            code = (exc.code if isinstance(exc, CardError) else
                    "REVIEW_REQUIRED" if type(exc).__name__ == "PasteQualityError" else "ANALYSIS_UNAVAILABLE")
            with self._lock:
                self._jobs[job_id].status = "failed"
                self._jobs[job_id].error_code = code
        else:
            with self._lock:
                self._jobs[job_id].result = copy.deepcopy(result)
                self._jobs[job_id].source = source
                self._jobs[job_id].status = "complete"
        finally:
            with self._lock:
                self._jobs[job_id].finished = self.clock()
                self._active -= 1

    def get(self, owner: str, job_id: str) -> dict[str, object] | None:
        with self._lock:
            self._prune()
            job = self._jobs.get(job_id)
            return job.public() if job is not None and job.owner == owner else None

    def context(self, owner: str, job_id: str) -> tuple[PasteRequest, dict] | None:
        """Owner-scoped snapshot for follow-ups; not a public API response."""
        with self._lock:
            self._prune()
            job = self._jobs.get(job_id)
            if (job is None or job.owner != owner or job.status != "complete"
                    or job.source is None or job.result is None):
                return None
            return job.source.model_copy(deep=True), copy.deepcopy(job.result)

    def close(self) -> None:
        self._stop.set()
        with self._lock:
            self._closed = True
        self._pool.shutdown(wait=True)
        self._janitor.join(timeout=2)
        with self._lock:
            self._jobs.clear()
            self._starts.clear()
