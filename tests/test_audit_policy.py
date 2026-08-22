from __future__ import annotations

from datetime import datetime, timezone

from database.production_audit import AuditCheck, ProductionAuditReport
from jobs.audit_production import _historical_worker_failures_as_warnings


def _report(*checks: AuditCheck) -> ProductionAuditReport:
    return ProductionAuditReport(
        service="web",
        generated_at=datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc),
        database_dialect="postgresql",
        counts={},
        latest_jobs={},
        version_counts={},
        checks=checks,
    )


def test_old_worker_error_can_warn_while_public_integrity_passes() -> None:
    report = _report(
        AuditCheck(
            code="LATEST_INGESTION_JOB",
            status="fail",
            message="Latest ingestion job failed.",
        ),
        AuditCheck(
            code="PUBLIC_SOURCE_LINKS",
            status="pass",
            message="Source links are valid.",
        ),
    )

    adjusted = _historical_worker_failures_as_warnings(report)
    checks = {item.code: item for item in adjusted.checks}

    assert adjusted.passed is True
    assert adjusted.warning_count == 1
    assert checks["LATEST_INGESTION_JOB"].status == "warning"
    assert "fresh post-deploy run" in checks["LATEST_INGESTION_JOB"].message


def test_public_integrity_error_remains_blocking() -> None:
    report = _report(
        AuditCheck(
            code="LATEST_INGESTION_JOB",
            status="fail",
            message="Latest ingestion job failed.",
        ),
        AuditCheck(
            code="PUBLIC_SOURCE_LINKS",
            status="fail",
            message="A source link is missing.",
        ),
    )

    adjusted = _historical_worker_failures_as_warnings(report)
    checks = {item.code: item for item in adjusted.checks}

    assert adjusted.passed is False
    assert adjusted.failure_count == 1
    assert checks["LATEST_INGESTION_JOB"].status == "warning"
    assert checks["PUBLIC_SOURCE_LINKS"].status == "fail"
