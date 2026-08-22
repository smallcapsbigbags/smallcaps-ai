from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import urlparse

from sqlalchemy import Engine, desc, func, insert, select
from sqlalchemy.orm import Session, sessionmaker

from analyst.version import ANALYSIS_VERSION, DEFAULT_PROMPT_VERSION
from database.db import session_scope
from database.models import (
    AnalystRunRow,
    AnnouncementRow,
    CompanyRow,
    FactRow,
    GuidanceEventRow,
    JobRunRow,
    ManagementClaimRow,
    PriceReactionRow,
)

AuditStatus = Literal["pass", "warning", "fail"]


@dataclass(frozen=True)
class AuditCheck:
    code: str
    status: AuditStatus
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProductionAuditReport:
    service: str
    generated_at: datetime
    database_dialect: str
    counts: dict[str, int]
    latest_jobs: dict[str, dict[str, object] | None]
    version_counts: dict[str, int]
    checks: tuple[AuditCheck, ...]

    @property
    def passed(self) -> bool:
        return not any(check.status == "fail" for check in self.checks)

    @property
    def warning_count(self) -> int:
        return sum(check.status == "warning" for check in self.checks)

    @property
    def failure_count(self) -> int:
        return sum(check.status == "fail" for check in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "service": self.service,
            "generated_at": self.generated_at.isoformat(),
            "database_dialect": self.database_dialect,
            "passed": self.passed,
            "warning_count": self.warning_count,
            "failure_count": self.failure_count,
            "counts": dict(self.counts),
            "latest_jobs": dict(self.latest_jobs),
            "version_counts": dict(self.version_counts),
            "expected_analysis_version": ANALYSIS_VERSION,
            "expected_prompt_version": DEFAULT_PROMPT_VERSION,
            "checks": [check.as_dict() for check in self.checks],
        }


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _valid_http_url(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _source_candidates(
    announcement: AnnouncementRow,
    run: AnalystRunRow,
) -> list[str]:
    values: list[object] = [
        announcement.source_url,
        *(announcement.source_urls or []),
        *(run.source_references or []),
    ]
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def _job_dict(row: JobRunRow | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "job_name": row.job_name,
        "run_key": row.run_key,
        "status": row.status,
        "started_at": _utc(row.started_at).isoformat() if row.started_at else None,
        "finished_at": _utc(row.finished_at).isoformat() if row.finished_at else None,
        "summary": dict(row.summary or {}),
        "warning_count": len(row.warnings or []),
        "has_error": bool((row.error_text or "").strip()),
    }


def _latest_job(session: Session, job_name: str) -> JobRunRow | None:
    return session.scalar(
        select(JobRunRow)
        .where(JobRunRow.job_name == job_name)
        .order_by(desc(JobRunRow.started_at))
        .limit(1)
    )


def _write_probe(engine: Engine) -> tuple[bool, str]:
    """Prove that production credentials can write without retaining probe data."""

    probe_id = uuid.uuid4()
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(
                    insert(JobRunRow).values(
                        id=probe_id,
                        job_name="production-audit-write-probe",
                        run_key=str(probe_id),
                        status="running",
                        summary={},
                        warnings=[],
                        error_text="",
                    )
                )
                found = connection.scalar(
                    select(func.count())
                    .select_from(JobRunRow)
                    .where(JobRunRow.id == probe_id)
                )
                transaction.rollback()
            except Exception:
                transaction.rollback()
                raise
        return bool(found == 1), ""
    except Exception as exc:  # pragma: no cover - exercised against live credentials
        return False, f"{type(exc).__name__}: {exc}"[:700]


def run_production_audit(
    engine: Engine,
    session_factory: sessionmaker[Session],
    *,
    service: str,
    market_data_enabled: bool,
    strict_production: bool,
    now: datetime | None = None,
) -> ProductionAuditReport:
    """Inspect the live operational record without calling OpenAI or market data."""

    current_time = _utc(now) or datetime.now(timezone.utc)
    checks: list[AuditCheck] = []

    if strict_production and engine.dialect.name != "postgresql":
        checks.append(
            AuditCheck(
                code="PRODUCTION_DATABASE",
                status="fail",
                message="Production must use PostgreSQL; SQLite is not persistent on Railway.",
                details={"dialect": engine.dialect.name},
            )
        )
    else:
        checks.append(
            AuditCheck(
                code="PRODUCTION_DATABASE",
                status="pass",
                message=f"Database dialect is {engine.dialect.name}.",
            )
        )

    writable, write_error = _write_probe(engine)
    checks.append(
        AuditCheck(
            code="DATABASE_WRITE_ROUNDTRIP",
            status="pass" if writable else "fail",
            message=(
                "Database write/rollback probe succeeded."
                if writable
                else "Database credentials could not complete a write/rollback probe."
            ),
            details={"error": write_error} if write_error else {},
        )
    )

    with session_scope(session_factory) as session:
        counts = {
            "companies": int(session.scalar(select(func.count()).select_from(CompanyRow)) or 0),
            "announcements": int(
                session.scalar(select(func.count()).select_from(AnnouncementRow)) or 0
            ),
            "analyst_runs": int(
                session.scalar(select(func.count()).select_from(AnalystRunRow)) or 0
            ),
            "current_publishable": int(
                session.scalar(
                    select(func.count())
                    .select_from(AnalystRunRow)
                    .where(
                        AnalystRunRow.is_current.is_(True),
                        AnalystRunRow.quality_status == "publishable",
                    )
                )
                or 0
            ),
            "current_review": int(
                session.scalar(
                    select(func.count())
                    .select_from(AnalystRunRow)
                    .where(
                        AnalystRunRow.is_current.is_(True),
                        AnalystRunRow.quality_status == "review",
                    )
                )
                or 0
            ),
            "facts": int(session.scalar(select(func.count()).select_from(FactRow)) or 0),
            "guidance_events": int(
                session.scalar(select(func.count()).select_from(GuidanceEventRow)) or 0
            ),
            "management_claims": int(
                session.scalar(select(func.count()).select_from(ManagementClaimRow)) or 0
            ),
            "price_reactions": int(
                session.scalar(select(func.count()).select_from(PriceReactionRow)) or 0
            ),
            "job_runs": int(session.scalar(select(func.count()).select_from(JobRunRow)) or 0),
        }

        version_rows = session.execute(
            select(AnalystRunRow.analysis_version, func.count())
            .where(AnalystRunRow.is_current.is_(True))
            .group_by(AnalystRunRow.analysis_version)
        ).all()
        version_counts = {
            str(version or "unknown"): int(count or 0)
            for version, count in version_rows
        }

        duplicate_current_rows = session.execute(
            select(AnalystRunRow.announcement_id, func.count())
            .where(AnalystRunRow.is_current.is_(True))
            .group_by(AnalystRunRow.announcement_id)
            .having(func.count() > 1)
        ).all()
        checks.append(
            AuditCheck(
                code="ONE_CURRENT_ANALYSIS",
                status="fail" if duplicate_current_rows else "pass",
                message=(
                    f"{len(duplicate_current_rows)} announcement(s) have multiple current analyses."
                    if duplicate_current_rows
                    else "Every announcement has at most one current analysis."
                ),
            )
        )

        current_rows = session.execute(
            select(AnnouncementRow, AnalystRunRow)
            .join(
                AnalystRunRow,
                AnalystRunRow.announcement_id == AnnouncementRow.id,
            )
            .where(AnalystRunRow.is_current.is_(True))
        ).all()

        invalid_quality = [
            announcement.source_id
            for announcement, run in current_rows
            if run.quality_status not in {"publishable", "review"}
        ]
        checks.append(
            AuditCheck(
                code="CURRENT_QUALITY_STATES",
                status="fail" if invalid_quality else "pass",
                message=(
                    "Current analyses contain unsupported quality states."
                    if invalid_quality
                    else "Current analyses use only publishable or review states."
                ),
                details={"source_ids": invalid_quality[:20]} if invalid_quality else {},
            )
        )

        unavailable_public = [
            announcement.source_id
            for announcement, run in current_rows
            if run.quality_status == "publishable"
            and announcement.evidence_status == "unavailable"
        ]
        checks.append(
            AuditCheck(
                code="NO_UNAVAILABLE_PUBLIC_EVIDENCE",
                status="fail" if unavailable_public else "pass",
                message=(
                    "A publishable analysis is backed by unavailable evidence."
                    if unavailable_public
                    else "No publishable analysis uses unavailable evidence."
                ),
                details={"source_ids": unavailable_public[:20]}
                if unavailable_public
                else {},
            )
        )

        missing_source_links: list[str] = []
        invalid_source_links: list[str] = []
        for announcement, run in current_rows:
            if run.quality_status != "publishable":
                continue
            candidates = _source_candidates(announcement, run)
            if not candidates:
                missing_source_links.append(announcement.source_id)
            elif not any(_valid_http_url(value) for value in candidates):
                invalid_source_links.append(announcement.source_id)
        source_failures = [*missing_source_links, *invalid_source_links]
        checks.append(
            AuditCheck(
                code="PUBLIC_SOURCE_LINKS",
                status="fail" if source_failures else "pass",
                message=(
                    f"{len(source_failures)} publishable announcement(s) lack a usable HTTP source link."
                    if source_failures
                    else "Every publishable announcement retains a usable source link."
                ),
                details={
                    "missing": missing_source_links[:20],
                    "invalid": invalid_source_links[:20],
                }
                if source_failures
                else {},
            )
        )

        weak_evidence = [
            announcement.source_id
            for announcement, run in current_rows
            if run.quality_status == "publishable"
            and announcement.evidence_status in {"complete", "partial"}
            and len((announcement.raw_text or "").strip()) < 40
        ]
        checks.append(
            AuditCheck(
                code="PUBLIC_EVIDENCE_LENGTH",
                status="fail" if weak_evidence else "pass",
                message=(
                    "A publishable non-metadata analysis has an implausibly short evidence record."
                    if weak_evidence
                    else "Publishable non-metadata analyses retain usable evidence text."
                ),
                details={"source_ids": weak_evidence[:20]} if weak_evidence else {},
            )
        )

        latest_publishable = session.execute(
            select(AnnouncementRow, AnalystRunRow)
            .join(
                AnalystRunRow,
                AnalystRunRow.announcement_id == AnnouncementRow.id,
            )
            .where(
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
            )
            .order_by(desc(AnnouncementRow.published_at))
            .limit(1)
        ).first()
        checks.append(
            AuditCheck(
                code="PUBLIC_FEED_HAS_DATA",
                status="pass" if latest_publishable else "fail",
                message=(
                    "The public Feed has at least one publishable announcement."
                    if latest_publishable
                    else "The public Feed has no publishable announcement."
                ),
                details={
                    "source_id": latest_publishable[0].source_id,
                    "published_at": _utc(latest_publishable[0].published_at).isoformat(),
                }
                if latest_publishable
                else {},
            )
        )

        if counts["current_review"]:
            checks.append(
                AuditCheck(
                    code="REVIEW_QUEUE",
                    status="warning",
                    message=f"{counts['current_review']} current analysis item(s) require owner review and remain hidden from public pages.",
                )
            )
        else:
            checks.append(
                AuditCheck(
                    code="REVIEW_QUEUE",
                    status="pass",
                    message="No current analysis item is waiting for owner review.",
                )
            )

        checks.append(
            AuditCheck(
                code="COMPANY_MEMORY_DATA",
                status=(
                    "pass"
                    if counts["facts"]
                    else "warning"
                ),
                message=(
                    "Structured facts are available for Company Memory."
                    if counts["facts"]
                    else "No structured fact has yet been stored for Company Memory."
                ),
                details={
                    "facts": counts["facts"],
                    "guidance_events": counts["guidance_events"],
                    "management_claims": counts["management_claims"],
                },
            )
        )

        current_version_count = version_counts.get(ANALYSIS_VERSION, 0)
        checks.append(
            AuditCheck(
                code="CURRENT_ANALYST_VERSION_OBSERVED",
                status="pass" if current_version_count else "warning",
                message=(
                    f"{current_version_count} current analysis record(s) were produced by {ANALYSIS_VERSION}."
                    if current_version_count
                    else f"No live RNS has yet been analysed by {ANALYSIS_VERSION}; the next eligible RNS will create the first record."
                ),
                details={"version_counts": version_counts},
            )
        )

        latest_ingestion = _latest_job(session, "daily-aim-ingestion")
        latest_prices = _latest_job(session, "daily-price-reactions")
        latest_jobs = {
            "daily-aim-ingestion": _job_dict(latest_ingestion),
            "daily-price-reactions": _job_dict(latest_prices),
        }

        stale_running = session.scalars(
            select(JobRunRow).where(
                JobRunRow.status == "running",
                JobRunRow.started_at < current_time - timedelta(hours=3),
            )
        ).all()
        checks.append(
            AuditCheck(
                code="NO_STUCK_JOBS",
                status="fail" if stale_running else "pass",
                message=(
                    f"{len(stale_running)} job run(s) have remained in running state for more than three hours."
                    if stale_running
                    else "No job run is stuck in running state."
                ),
                details={"job_ids": [str(row.id) for row in stale_running[:20]]}
                if stale_running
                else {},
            )
        )

        if latest_ingestion is None:
            checks.append(
                AuditCheck(
                    code="LATEST_INGESTION_JOB",
                    status="warning",
                    message="No completed ingestion job has yet been recorded.",
                )
            )
        else:
            ingestion_started = _utc(latest_ingestion.started_at) or current_time
            age_hours = max(
                0.0,
                (current_time - ingestion_started).total_seconds() / 3600,
            )
            ingestion_status: AuditStatus = (
                "fail" if latest_ingestion.status == "failed" else "pass"
            )
            if age_hours > 96 and ingestion_status == "pass":
                ingestion_status = "warning"
            checks.append(
                AuditCheck(
                    code="LATEST_INGESTION_JOB",
                    status=ingestion_status,
                    message=(
                        f"Latest ingestion job is {latest_ingestion.status} and started {age_hours:.1f} hours ago."
                    ),
                    details=_job_dict(latest_ingestion) or {},
                )
            )

        if not market_data_enabled:
            checks.append(
                AuditCheck(
                    code="MARKET_DATA_OPERATION",
                    status="warning",
                    message="Market-data collection is disabled by configuration.",
                )
            )
        elif latest_prices is None:
            checks.append(
                AuditCheck(
                    code="MARKET_DATA_OPERATION",
                    status="warning",
                    message="No price-reaction worker run has yet been recorded.",
                )
            )
        else:
            price_started = _utc(latest_prices.started_at) or current_time
            age_hours = max(
                0.0,
                (current_time - price_started).total_seconds() / 3600,
            )
            price_status: AuditStatus = (
                "fail" if latest_prices.status == "failed" else "pass"
            )
            if age_hours > 120 and price_status == "pass":
                price_status = "warning"
            checks.append(
                AuditCheck(
                    code="MARKET_DATA_OPERATION",
                    status=price_status,
                    message=(
                        f"Latest price-reaction job is {latest_prices.status} and started {age_hours:.1f} hours ago."
                    ),
                    details=_job_dict(latest_prices) or {},
                )
            )

        if market_data_enabled and counts["price_reactions"] == 0:
            checks.append(
                AuditCheck(
                    code="PRICE_REACTION_DATA",
                    status="warning",
                    message="Market data is enabled but no price reaction has yet been stored.",
                )
            )
        else:
            checks.append(
                AuditCheck(
                    code="PRICE_REACTION_DATA",
                    status="pass",
                    message=f"{counts['price_reactions']} price reaction record(s) are stored.",
                )
            )

    return ProductionAuditReport(
        service=service,
        generated_at=current_time,
        database_dialect=engine.dialect.name,
        counts=counts,
        latest_jobs=latest_jobs,
        version_counts=version_counts,
        checks=tuple(checks),
    )
