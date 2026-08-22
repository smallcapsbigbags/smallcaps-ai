from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from database.db import session_scope
from database.models import AnalystRunRow, AnnouncementRow, CorrectionRow

SAFETY_FLAG_CODE = "PUBLICATION_SAFETY_REVIEW"


@dataclass(frozen=True)
class PublicationSafetyResult:
    inspected: int = 0
    moved_to_review: int = 0
    source_ids: tuple[str, ...] = ()
    reasons: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "inspected": self.inspected,
            "moved_to_review": self.moved_to_review,
            "source_ids": list(self.source_ids),
            "reasons": {
                source_id: list(items)
                for source_id, items in self.reasons.items()
            },
        }


def _valid_http_url(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    parsed = urlparse(text)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


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


def publication_safety_reasons(
    announcement: AnnouncementRow,
    run: AnalystRunRow,
) -> tuple[str, ...]:
    """Return deterministic reasons a current record cannot remain public."""

    reasons: list[str] = []
    evidence_status = str(announcement.evidence_status or "").strip().lower()
    if evidence_status == "unavailable":
        reasons.append("The stored evidence status is unavailable.")
    if (
        evidence_status in {"complete", "partial"}
        and len((announcement.raw_text or "").strip()) < 40
    ):
        reasons.append("The stored evidence text is too short for public analysis.")

    candidates = _source_candidates(announcement, run)
    if not candidates:
        reasons.append("No original source link is stored.")
    elif not any(_valid_http_url(value) for value in candidates):
        reasons.append("No stored source link is a usable HTTP(S) URL.")

    return tuple(reasons)


def reconcile_publication_safety(
    session_factory: sessionmaker[Session],
    *,
    corrected_by: str = "system-publication-safety",
) -> PublicationSafetyResult:
    """Move unsafe current publishable records to the owner review queue.

    This is intentionally conservative. It never deletes research and never edits
    reported facts. It only changes public eligibility, appends an explicit quality
    flag and creates a correction audit record. Future page reads therefore remain
    available while questionable legacy rows fail closed.
    """

    moved: list[str] = []
    reason_map: dict[str, tuple[str, ...]] = {}

    with session_scope(session_factory) as session:
        rows = session.execute(
            select(AnnouncementRow, AnalystRunRow)
            .join(
                AnalystRunRow,
                AnalystRunRow.announcement_id == AnnouncementRow.id,
            )
            .where(
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
            )
        ).all()

        for announcement, run in rows:
            reasons = publication_safety_reasons(announcement, run)
            if not reasons:
                continue

            original_flags = list(run.quality_flags or [])
            flag = {
                "code": SAFETY_FLAG_CODE,
                "severity": "review",
                "message": " ".join(reasons),
            }
            if not any(
                str(item.get("code") or "") == SAFETY_FLAG_CODE
                for item in original_flags
                if isinstance(item, dict)
            ):
                run.quality_flags = [*original_flags, flag]
            run.quality_status = "review"

            session.add(
                CorrectionRow(
                    analyst_run_id=run.id,
                    field_path="quality_status",
                    original_value={
                        "quality_status": "publishable",
                        "quality_flags": original_flags,
                    },
                    corrected_value={
                        "quality_status": "review",
                        "quality_flag": flag,
                    },
                    reason=(
                        "Automatically removed from public pages by the launch "
                        "publication-safety check: " + " ".join(reasons)
                    ),
                    corrected_by=corrected_by,
                )
            )
            moved.append(announcement.source_id)
            reason_map[announcement.source_id] = reasons

        session.flush()

    return PublicationSafetyResult(
        inspected=len(rows),
        moved_to_review=len(moved),
        source_ids=tuple(moved),
        reasons=reason_map,
    )
