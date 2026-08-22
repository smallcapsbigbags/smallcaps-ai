from __future__ import annotations

from collections.abc import Mapping


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


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
