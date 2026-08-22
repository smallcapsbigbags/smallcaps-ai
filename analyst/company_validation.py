from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from analyst.company_context import build_company_analysis_context
from analyst.models import AnnouncementInput


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = _clean(value)
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dict_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _source_ids(value: object, output: set[str]) -> None:
    if isinstance(value, Mapping):
        source_id = value.get("source_id")
        if isinstance(source_id, str) and source_id.strip():
            output.add(source_id.strip())
        for nested in value.values():
            _source_ids(nested, output)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            _source_ids(nested, output)


def _announcement_from_record(
    record: Mapping[str, object],
    *,
    ticker: str,
    company: str,
) -> AnnouncementInput:
    published_at = _parse_datetime(record.get("published_at"))
    if published_at is None:
        raise ValueError("record has no valid published_at")
    source_id = _clean(record.get("source_id"))
    title = _clean(record.get("title") or record.get("headline"))
    text = _clean(
        record.get("raw_text")
        or record.get("text")
        or record.get("takeaway")
        or title
    )
    source_urls = [
        str(item).strip()
        for item in (record.get("source_urls") or [])
        if str(item).strip()
    ]
    source_url = _clean(record.get("source_url"))
    if source_url and source_url not in source_urls:
        source_urls.append(source_url)
    categories = [
        str(item).strip()
        for item in (record.get("categories") or [])
        if str(item).strip()
    ]
    return AnnouncementInput(
        source_id=source_id,
        ticker=ticker,
        company=company,
        published_at=published_at,
        title=title,
        text=text,
        source_url=source_url,
        source_urls=source_urls,
        source_note=_clean(record.get("source_note")),
        evidence_status=str(record.get("evidence_status") or "complete"),
        rns_type=_clean(record.get("rns_type") or "Other"),
        categories=categories,
    )


def _comparator_source_ids(record: Mapping[str, object]) -> set[str]:
    output: set[str] = set()
    for fact in _dict_items(record.get("facts")):
        source_id = _clean(fact.get("comparator_source_id"))
        if source_id:
            output.add(source_id)
    for event in _dict_items(record.get("guidance")):
        source_id = _clean(event.get("previous_source_id"))
        if source_id:
            output.add(source_id)
    return output


def _claim_statuses(record: Mapping[str, object]) -> dict[str, str]:
    output: dict[str, str] = {}
    for claim in _dict_items(record.get("management_claims")):
        key = _clean(claim.get("claim_key"))
        status = _clean(claim.get("status") or "open").lower()
        if key:
            output[key] = status
    return output


def validate_company_timeline(
    records: Sequence[Mapping[str, object]],
    *,
    ticker: str,
    company: str,
    history_limit: int = 7,
) -> dict[str, object]:
    """Reconstruct the exact prior context at every covered announcement.

    This validator makes no model call. It checks that production context assembly
    is point-in-time safe, that structured comparator source IDs are traceable,
    and that the memory snapshot remains internally consistent as coverage grows.
    The full timeline is deliberately supplied at every step so the shared context
    builder must reject the current and future announcements itself.
    """

    clean_ticker = _clean(ticker).upper().replace(".L", "").rstrip(".-")
    global_errors: list[str] = []
    global_warnings: list[str] = []
    parsed_records: list[tuple[datetime, dict[str, object]]] = []
    seen_source_ids: set[str] = set()

    for index, raw_record in enumerate(records):
        record = dict(raw_record)
        source_id = _clean(record.get("source_id"))
        published_at = _parse_datetime(record.get("published_at"))
        if not source_id:
            global_errors.append(f"record {index} has no source_id")
            continue
        if source_id in seen_source_ids:
            global_errors.append(f"duplicate source_id {source_id!r}")
            continue
        seen_source_ids.add(source_id)
        if published_at is None:
            global_errors.append(f"record {source_id!r} has invalid published_at")
            continue
        parsed_records.append((published_at, record))

    parsed_records.sort(key=lambda item: item[0])
    ordered = [record for _published_at, record in parsed_records]
    points: list[dict[str, object]] = []
    resolved_claims: dict[str, str] = {}

    for index, current in enumerate(ordered):
        point_errors: list[str] = []
        point_warnings: list[str] = []
        source_id = _clean(current.get("source_id"))
        try:
            announcement = _announcement_from_record(
                current,
                ticker=clean_ticker,
                company=company,
            )
        except (TypeError, ValueError) as exc:
            global_errors.append(f"record {source_id!r}: {exc}")
            continue

        bundle = build_company_analysis_context(
            ordered,
            announcement,
            history_limit=history_limit,
        )
        eligible_ids = {
            _clean(record.get("source_id"))
            for record in bundle.eligible_records
            if _clean(record.get("source_id"))
        }
        expected_eligible_ids = {
            _clean(record.get("source_id"))
            for record in ordered[:index]
            if _clean(record.get("source_id"))
        }
        if eligible_ids != expected_eligible_ids:
            point_errors.append(
                "eligible prior source IDs do not match the strictly earlier timeline"
            )
        if source_id in eligible_ids or source_id in bundle.selected_source_ids:
            point_errors.append("the current RNS entered its own prior context")

        context_source_ids: set[str] = set()
        _source_ids(bundle.context_records, context_source_ids)
        future_ids = {
            _clean(record.get("source_id"))
            for record in ordered[index:]
            if _clean(record.get("source_id"))
        }
        leaked = sorted(context_source_ids & future_ids)
        if leaked:
            point_errors.append(
                "current/future source IDs leaked into context: " + ", ".join(leaked)
            )
        unknown_context_ids = sorted(context_source_ids - eligible_ids)
        if unknown_context_ids:
            point_errors.append(
                "context contains source IDs outside eligible history: "
                + ", ".join(unknown_context_ids)
            )

        memory = bundle.memory
        if index == 0:
            if memory is not None or bundle.context_records:
                point_errors.append("first covered RNS should have no prior company memory")
            coverage_status = "building"
            metric_count = 0
            guidance_count = 0
            open_claim_count = 0
        else:
            if memory is None:
                point_errors.append("eligible history exists but no memory snapshot was built")
                coverage_status = "building"
                metric_count = 0
                guidance_count = 0
                open_claim_count = 0
            else:
                coverage_status = memory.coverage_status
                metric_count = len(memory.metric_series)
                guidance_count = len(memory.current_guidance)
                open_claim_count = len(memory.open_management_claims)
                if memory.announcement_count != index:
                    point_errors.append(
                        f"memory announcement_count={memory.announcement_count}, expected {index}"
                    )
                generated_before = _parse_datetime(memory.generated_before)
                if generated_before != announcement.published_at.astimezone(timezone.utc):
                    point_errors.append("memory generated_before does not match current RNS time")
                latest_covered = _parse_datetime(memory.latest_covered_at)
                if latest_covered is not None and latest_covered >= announcement.published_at.astimezone(
                    timezone.utc
                ):
                    point_errors.append("memory includes a record at or after the current RNS")
                expected_status = (
                    "established"
                    if memory.announcement_count >= 6 and memory.coverage_days >= 365
                    else "building"
                )
                if memory.coverage_status != expected_status:
                    point_errors.append(
                        f"coverage_status={memory.coverage_status!r}, expected {expected_status!r}"
                    )
                if index >= 2 and not (
                    memory.metric_series
                    or memory.current_guidance
                    or memory.open_management_claims
                    or memory.resolved_management_claims
                ):
                    point_warnings.append(
                        "multiple prior RNSs exist but structured memory has no KPI, guidance or claim yield"
                    )

        comparator_ids = _comparator_source_ids(current)
        allowed_comparators = {*eligible_ids, source_id}
        unsupported_comparators = sorted(comparator_ids - allowed_comparators)
        if unsupported_comparators:
            point_errors.append(
                "stored analysis cites comparator source IDs outside eligible history: "
                + ", ".join(unsupported_comparators)
            )

        claim_statuses = _claim_statuses(current)
        for claim_key, status in claim_statuses.items():
            previous_status = resolved_claims.get(claim_key)
            if previous_status and status == "open":
                point_warnings.append(
                    f"claim {claim_key!r} re-opened after status {previous_status!r}"
                )
            if status in {"delivered", "missed", "superseded", "not-assessable"}:
                resolved_claims[claim_key] = status

        if len(bundle.selected_source_ids) > max(0, history_limit):
            point_errors.append("selected prior context exceeds history_limit")
        selected_dates = [
            _parse_datetime(record.get("published_at"))
            for record in bundle.eligible_records
            if _clean(record.get("source_id")) in set(bundle.selected_source_ids)
        ]
        selected_dates = [item for item in selected_dates if item is not None]
        if selected_dates != sorted(selected_dates):
            point_errors.append("selected prior records are not chronological")

        points.append(
            {
                "source_id": source_id,
                "published_at": announcement.published_at.isoformat(),
                "rns_type": announcement.rns_type,
                "eligible_prior_count": len(eligible_ids),
                "selected_prior_source_ids": list(bundle.selected_source_ids),
                "rejected_source_ids": list(bundle.rejected_source_ids),
                "coverage_status": coverage_status,
                "metric_series_count": metric_count,
                "current_guidance_count": guidance_count,
                "open_claim_count": open_claim_count,
                "cited_comparator_source_ids": sorted(comparator_ids),
                "errors": point_errors,
                "warnings": point_warnings,
                "valid": not point_errors,
            }
        )
        global_errors.extend(f"{source_id}: {message}" for message in point_errors)
        global_warnings.extend(f"{source_id}: {message}" for message in point_warnings)

    event_types = sorted(
        {
            _clean(record.get("rns_type") or "Other")
            for record in ordered
            if _clean(record.get("rns_type") or "Other")
        }
    )
    return {
        "ticker": clean_ticker,
        "company": company,
        "announcement_count": len(ordered),
        "checked_points": len(points),
        "event_types": event_types,
        "event_type_count": len(event_types),
        "errors": global_errors,
        "warnings": global_warnings,
        "points": points,
        "valid": not global_errors and len(points) == len(ordered),
    }
