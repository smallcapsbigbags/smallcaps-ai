from __future__ import annotations

from collections.abc import Sequence

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    QualityFlag,
    QualityReport,
    QualityStatus,
)


def _status(flags: list[QualityFlag]) -> QualityStatus:
    if any(flag.severity == "block" for flag in flags):
        return "blocked"
    if any(flag.severity == "review" for flag in flags):
        return "review"
    return "publishable"


def assess_analysis_quality(
    announcement: AnnouncementInput,
    note: AnalystNote,
    *,
    prior_context: Sequence[dict[str, object]] = (),
) -> QualityReport:
    """Apply deterministic publication checks after model validation and guardrails."""

    flags: list[QualityFlag] = []

    if announcement.evidence_status == "partial":
        flags.append(
            QualityFlag(
                code="PARTIAL_EVIDENCE",
                severity="review",
                message="The evidence dossier is partial and should be source-checked.",
            )
        )
    elif announcement.evidence_status == "unavailable":
        flags.append(
            QualityFlag(
                code="NO_EVIDENCE",
                severity="block",
                message="No usable source evidence is available.",
            )
        )

    for warning in note.source_warnings:
        if warning.startswith("GUARDRAIL:"):
            flags.append(
                QualityFlag(
                    code="GUARDRAIL_FAILURE",
                    severity="block",
                    message=warning,
                )
            )

    if note.confidence < 0.55:
        flags.append(
            QualityFlag(
                code="LOW_CONFIDENCE",
                severity="block",
                message=f"Model confidence {note.confidence:.2f} is below 0.55.",
            )
        )
    elif note.confidence < 0.75:
        flags.append(
            QualityFlag(
                code="REVIEW_CONFIDENCE",
                severity="review",
                message=f"Model confidence {note.confidence:.2f} is below 0.75.",
            )
        )

    if not note.impact_rationale.strip():
        flags.append(
            QualityFlag(
                code="MISSING_IMPACT_RATIONALE",
                severity="review",
                message="Impact has no explicit rationale.",
            )
        )

    if note.impact_score >= 3 and not note.impact_drivers:
        flags.append(
            QualityFlag(
                code="MISSING_IMPACT_DRIVERS",
                severity="review",
                message="High/Critical Impact requires at least one structured driver.",
            )
        )

    if note.rns_type not in {"Corporate", "Share capital"} and not note.key_facts:
        flags.append(
            QualityFlag(
                code="NO_KEY_FACTS",
                severity="review",
                message="No key facts were extracted for an investment-relevant announcement.",
            )
        )

    if (
        note.what_changed.coverage_status == "established"
        and not prior_context
    ):
        flags.append(
            QualityFlag(
                code="UNSUPPORTED_ESTABLISHED_COVERAGE",
                severity="block",
                message="What Changed claims established history but no prior context was supplied.",
            )
        )

    if (
        announcement.evidence_status != "metadata-only"
        and not note.source_references
    ):
        flags.append(
            QualityFlag(
                code="MISSING_SOURCE_REFERENCE",
                severity="review",
                message="The Analyst Note does not retain a source reference.",
            )
        )

    if note.disclosure_assessment.status == "insufficient":
        flags.append(
            QualityFlag(
                code="INSUFFICIENT_DISCLOSURE",
                severity="review",
                message="The announcement does not disclose enough information for a firm read-through.",
            )
        )

    for fact in note.key_facts:
        if fact.basis == "source-warning":
            flags.append(
                QualityFlag(
                    code="SOURCE_INCONSISTENCY",
                    severity="review",
                    message=f"Source inconsistency recorded for fact '{fact.label}'.",
                )
            )

    deduped: list[QualityFlag] = []
    seen: set[tuple[str, str]] = set()
    for flag in flags:
        key = (flag.code, flag.message)
        if key not in seen:
            seen.add(key)
            deduped.append(flag)

    return QualityReport(status=_status(deduped), flags=deduped)
