from __future__ import annotations

import hashlib
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Engine, desc, select, text
from sqlalchemy.orm import Session, sessionmaker

from database.db import session_scope
from database.models import JobRunRow

_LOCAL_LOCKS: dict[str, threading.Lock] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()


def _postgres_lock_key(name: str) -> int:
    value = int.from_bytes(
        hashlib.sha256(name.encode("utf-8")).digest()[:8],
        byteorder="big",
        signed=False,
    )
    return value - (1 << 64) if value >= (1 << 63) else value


@contextmanager
def advisory_job_lock(engine: Engine, name: str) -> Iterator[bool]:
    if engine.dialect.name == "postgresql":
        connection = engine.connect()
        key = _postgres_lock_key(name)
        acquired = bool(
            connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"),
                {"key": key},
            )
        )
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": key},
                )
            connection.close()
        return

    with _LOCAL_LOCKS_GUARD:
        lock = _LOCAL_LOCKS.setdefault(name, threading.Lock())
    acquired = lock.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()


class OperationsRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def reconcile_stale_running(
        self,
        *,
        job_name: str | None = None,
        max_age: timedelta = timedelta(hours=3),
        now: datetime | None = None,
    ) -> int:
        """Close job rows left running after a crashed or terminated worker.

        PostgreSQL advisory locks are released when a process dies, but the durable
        job row cannot update itself. Reconciling it before the next run prevents an
        old crash from looking like a worker that is still active forever.
        """

        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        cutoff = current - max_age
        with session_scope(self.session_factory) as session:
            query = select(JobRunRow).where(
                JobRunRow.status == "running",
                JobRunRow.started_at < cutoff,
            )
            if job_name:
                query = query.where(JobRunRow.job_name == job_name)
            rows = session.scalars(query).all()
            for row in rows:
                warning = (
                    "This run was automatically closed because the worker did not "
                    "record completion before the stale-run threshold."
                )
                row.status = "failed"
                row.finished_at = current
                row.warnings = [*list(row.warnings or []), warning]
                if not (row.error_text or "").strip():
                    row.error_text = "Worker exited or was terminated before completion."
            session.flush()
            return len(rows)

    def begin_job(
        self,
        job_name: str,
        *,
        run_key: str = "",
        summary: dict[str, object] | None = None,
    ) -> str:
        with session_scope(self.session_factory) as session:
            row = JobRunRow(
                job_name=job_name,
                run_key=run_key,
                status="running",
                summary=summary or {},
            )
            session.add(row)
            session.flush()
            return str(row.id)

    def finish_job(
        self,
        run_id: str,
        *,
        status: str,
        summary: dict[str, object] | None = None,
        warnings: list[str] | None = None,
        error_text: str = "",
    ) -> dict[str, Any]:
        if status not in {"success", "degraded", "failed", "skipped"}:
            raise ValueError(f"Unsupported job status: {status}")
        with session_scope(self.session_factory) as session:
            row = session.get(JobRunRow, uuid.UUID(run_id))
            if row is None:
                raise LookupError(f"Unknown job run: {run_id}")
            row.status = status
            row.finished_at = datetime.now(timezone.utc)
            row.summary = summary or {}
            row.warnings = warnings or []
            row.error_text = error_text[:4000]
            session.flush()
            return self._as_dict(row)

    def list_recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            rows = session.scalars(
                select(JobRunRow)
                .order_by(desc(JobRunRow.started_at))
                .limit(limit)
            ).all()
            return [self._as_dict(row) for row in rows]

    @staticmethod
    def _as_dict(row: JobRunRow) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "job_name": row.job_name,
            "run_key": row.run_key,
            "status": row.status,
            "started_at": row.started_at.isoformat(),
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "summary": dict(row.summary or {}),
            "warnings": list(row.warnings or []),
            "error_text": row.error_text,
        }
