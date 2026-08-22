from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from analyst.company_memory import CompanyMemorySnapshot, build_company_memory
from analyst.context_selector import select_prior_context
from analyst.models import AnnouncementInput


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _published_at(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _source_id(record: Mapping[str, object]) -> str:
    return str(record.get("source_id") or "").strip()


def build_prior_context_record(
    record: Mapping[str, object],
) -> dict[str, object]:
    """Separate prior company disclosure from earlier Smallcaps.ai interpretation.

    The repository record is intentionally rich because it is also used to build
    deterministic memory. Before sending selected records to the model, this
    function makes provenance explicit so an old analyst view cannot silently
    become a company-reported fact in a later note.
    """

    facts = _dict_list(record.get("facts"))
    reported_facts = [item for item in facts if item.get("basis") == "reported"]
    calculated_facts = [item for item in facts if item.get("basis") == "calculated"]
    fact_caveats = [
        item
        for item in facts
        if item.get("basis") not in {"reported", "calculated"}
    ]
    return {
        "context_type": "prior_company_record",
        "source_id": record.get("source_id"),
        "published_at": record.get("published_at"),
        "title": record.get("title"),
        "source_url": record.get("source_url"),
        "source_urls": list(record.get("source_urls") or []),
        "rns_type": record.get("rns_type"),
        "company_disclosure": {
            "reported_facts": reported_facts,
            "guidance_events": _dict_list(record.get("guidance")),
            "management_claims": _dict_list(record.get("management_claims")),
        },
        "smallcaps_calculations": calculated_facts,
        "source_caveats": fact_caveats,
        "prior_smallcaps_analysis": {
            "impact_colour": record.get("impact_colour"),
            "impact_score": record.get("impact_score"),
            "impact_rationale": record.get("impact_rationale"),
            "headline": record.get("headline"),
            "takeaway": record.get("takeaway"),
            "new_information": list(record.get("new_information") or []),
            "reiterated_information": list(
                record.get("reiterated_information") or []
            ),
            "what_changed": dict(record.get("what_changed") or {}),
            "analyst_view": record.get("analyst_view"),
            "supports_case": list(record.get("supports_case") or []),
            "challenges_case": list(record.get("challenges_case") or []),
            "watch_items": list(record.get("watch_items") or []),
            "disclosure_assessment": dict(
                record.get("disclosure_assessment") or {}
            ),
        },
        "context_rules": [
            "company_disclosure contains structured company-reported history",
            "smallcaps_calculations contains earlier arithmetic, not reported facts",
            "prior_smallcaps_analysis is earlier interpretation and must not be presented as company disclosure",
        ],
    }


@dataclass(frozen=True)
class CompanyAnalysisContext:
    """Deterministic point-in-time context supplied to one Analyst Engine call."""

    eligible_records: tuple[dict[str, object], ...]
    context_records: tuple[dict[str, object], ...]
    memory: CompanyMemorySnapshot | None
    selected_source_ids: tuple[str, ...]
    rejected_source_ids: tuple[str, ...]
    expected_coverage_status: str

    def as_list(self) -> list[dict[str, object]]:
        return list(self.context_records)


def eligible_prior_records(
    records: Sequence[Mapping[str, object]],
    announcement: AnnouncementInput,
) -> tuple[list[dict[str, object]], list[str]]:
    """Filter and order history defensively before it can reach company memory.

    The repository already applies ``published_at < current RNS``. This second
    boundary protects tests, manual jobs and future adapters from accidentally
    supplying the current announcement, a later announcement, a duplicate source
    or a record belonging to another ticker.
    """

    current_at = announcement.published_at.astimezone(timezone.utc)
    current_source_id = announcement.source_id.strip()
    ticker = announcement.ticker.upper()
    accepted: dict[str, dict[str, object]] = {}
    rejected: list[str] = []

    for index, raw_record in enumerate(records):
        record = dict(raw_record)
        source_id = _source_id(record)
        rejection_label = source_id or f"<missing-source-id:{index}>"
        published_at = _published_at(record.get("published_at"))
        record_ticker = str(record.get("ticker") or "").upper().strip()

        if (
            not source_id
            or source_id == current_source_id
            or published_at is None
            or published_at >= current_at
            or (record_ticker and record_ticker != ticker)
            or source_id in accepted
        ):
            rejected.append(rejection_label)
            continue
        accepted[source_id] = record

    ordered = sorted(
        accepted.values(),
        key=lambda item: _published_at(item.get("published_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
    )
    return ordered, list(dict.fromkeys(rejected))


def build_company_analysis_context(
    records: Sequence[Mapping[str, object]],
    announcement: AnnouncementInput,
    *,
    history_limit: int = 7,
) -> CompanyAnalysisContext:
    """Build the exact memory + selected-history payload for a new RNS.

    This is the single construction path used by production analysis and the
    Phase 3 live-validation job. Keeping both on the same function prevents a
    validator from proving behaviour different from the behaviour deployed.
    """

    eligible, rejected = eligible_prior_records(records, announcement)
    if not eligible:
        return CompanyAnalysisContext(
            eligible_records=(),
            context_records=(),
            memory=None,
            selected_source_ids=(),
            rejected_source_ids=tuple(rejected),
            expected_coverage_status="building",
        )

    memory = build_company_memory(
        eligible,
        ticker=announcement.ticker,
        company=announcement.company,
        before=announcement.published_at,
    )
    selected = select_prior_context(
        eligible,
        [announcement],
        limit=max(0, history_limit),
    )
    selected_source_ids = tuple(
        source_id
        for record in selected
        if (source_id := _source_id(record))
    )
    prior_records = tuple(build_prior_context_record(record) for record in selected)
    context_records = (memory.to_context_record(), *prior_records)
    return CompanyAnalysisContext(
        eligible_records=tuple(eligible),
        context_records=context_records,
        memory=memory,
        selected_source_ids=selected_source_ids,
        rejected_source_ids=tuple(rejected),
        expected_coverage_status=memory.coverage_status,
    )
