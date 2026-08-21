from __future__ import annotations

import re
from collections.abc import Iterable

from analyst.models import AnalystNote, AnnouncementInput

_GUIDANCE_STATUSES = {
    "issued",
    "reiterated",
    "upgraded",
    "downgraded",
    "maintained",
    "withdrawn",
    "delivered",
    "missed",
}
_ASPIRATION_RE = re.compile(
    r"\b(?:aims?|hopes?|intends?|aspires?|seeks?|plans? to consider|may consider)\b",
    re.IGNORECASE,
)
_TIMEFRAME_RE = re.compile(
    r"\b(?:FY\s?\d{2,4}|H[12]|Q[1-4]|20\d{2}|by (?:the end of )?[A-Z][a-z]+|"
    r"by year[- ]end|within \d+ (?:days?|weeks?|months?|years?)|through FY\s?\d{2,4})\b",
    re.IGNORECASE,
)
_MEASURABLE_RE = re.compile(
    r"(?:£|\$|€)\s?\d|\b\d+(?:\.\d+)?\s?(?:%|p|m|bn|million|billion|"
    r"boepd|tonnes?|units?)\b|\b\d+(?:\.\d+)?\s*(?:-|–|to)\s*\d+(?:\.\d+)?",
    re.IGNORECASE,
)
_FORWARD_MARKER_RE = re.compile(
    r"\b(?:expects?|expected|anticipates?|anticipated|forecasts?|forecast|guidance|"
    r"target|projects?|projected|will|aims?|hopes?|intends?|aspires?|seeks?)\b",
    re.IGNORECASE,
)
_COMPARATIVE_GUIDANCE_RE = re.compile(
    r"\b(?:ahead|below|above|higher|lower|exceed|grow|decline|in line)\b",
    re.IGNORECASE,
)
_COMMITTED_ACTION_RE = re.compile(
    r"\bwill\b.{0,80}\b(?:complete|commence|launch|pay|resume|close)\b",
    re.IGNORECASE,
)

_ADVERSE_RULES: tuple[tuple[str, re.Pattern[str], tuple[str, ...]], ...] = (
    (
        "covenant breach",
        re.compile(
            r"(?:\bcovenants?\b.{0,100}\b(?:breach|breached|waiver|non[- ]compliance|not compliant)\b|"
            r"\b(?:breach|breached)\b.{0,100}\bcovenants?\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        ("covenant", "waiver", "non-compliance", "not compliant"),
    ),
    (
        "debt repayable on demand",
        re.compile(r"\b(?:repayable|payable|due) on demand\b", re.IGNORECASE),
        ("on demand",),
    ),
    (
        "material going-concern uncertainty",
        re.compile(
            r"(?:\bmaterial uncertainty\b.{0,100}\bgoing concern\b|"
            r"\bgoing concern\b.{0,100}\bmaterial uncertainty\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        ("going concern", "material uncertainty"),
    ),
    (
        "insufficient working capital",
        re.compile(r"\binsufficient working capital\b", re.IGNORECASE),
        ("working capital", "insufficient"),
    ),
    (
        "fully drawn facility",
        re.compile(
            r"(?:\bfully drawn\b.{0,80}\b(?:facility|facilities|loan|debt)\b|"
            r"\b(?:facility|facilities|loan|debt)\b.{0,80}\bfully drawn\b)",
            re.IGNORECASE | re.DOTALL,
        ),
        ("fully drawn",),
    ),
    (
        "emergency or rescue financing",
        re.compile(
            r"\b(?:emergency|rescue) (?:finance|financing|funding)\b",
            re.IGNORECASE,
        ),
        ("emergency", "rescue"),
    ),
    (
        "adverse audit language",
        re.compile(
            r"\b(?:qualified opinion|adverse opinion|disclaimer of opinion|audit qualification)\b",
            re.IGNORECASE,
        ),
        ("qualified", "adverse opinion", "disclaimer", "audit qualification"),
    ),
    (
        "formal profit warning",
        re.compile(r"\bprofit warning\b", re.IGNORECASE),
        ("profit warning",),
    ),
    (
        "material customer loss",
        re.compile(
            r"\b(?:lost|loss of) (?:a |the )?(?:material|major|largest|key) customer\b",
            re.IGNORECASE,
        ),
        ("customer", "lost", "loss"),
    ),
    (
        "material contract termination",
        re.compile(
            r"\bcontract\b.{0,100}\b(?:terminated|termination|cancelled|cancellation)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        ("contract", "terminated", "termination", "cancelled", "cancellation"),
    ),
    (
        "material licence loss",
        re.compile(
            r"\blicen[cs]e\b.{0,100}\b(?:revoked|withdrawn|lost|terminated)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        ("licence", "license", "revoked", "withdrawn", "lost", "terminated"),
    ),
    (
        "insolvency risk",
        re.compile(
            r"\b(?:risk of|may enter|could enter) (?:administration|insolvency|liquidation)\b",
            re.IGNORECASE,
        ),
        ("administration", "insolvency", "liquidation"),
    ),
    (
        "explicit funding requirement",
        re.compile(
            r"\b(?:requires?|will require|needs?|will need) (?:additional |further )?"
            r"(?:funding|finance|capital)\b|\bfunding requirement\b",
            re.IGNORECASE,
        ),
        ("funding", "finance", "capital"),
    ),
    (
        "material refinancing deadline",
        re.compile(
            r"\brefinanc\w*\b.{0,100}\b(?:deadline|by|before|maturity|matures)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        ("refinanc", "maturity", "matures"),
    ),
)


def _note_text(note: AnalystNote) -> str:
    parts = [
        note.headline,
        note.takeaway,
        note.impact_rationale,
        note.what_changed.before,
        note.what_changed.today,
        note.what_changed.read_through,
        note.analyst_view,
        note.disclosure_assessment.management_language_mismatch,
        note.disclosure_assessment.note,
        *note.new_information,
        *note.reiterated_information,
        *note.supports_case,
        *note.challenges_case,
        *note.watch_items,
        *note.disclosure_assessment.missing_items,
    ]
    for driver in note.impact_drivers:
        parts.extend((driver.dimension, driver.direction, driver.rationale))
    for fact in note.key_facts:
        parts.extend(
            (
                fact.label,
                fact.value,
                fact.note,
                fact.comparator,
                fact.previous_value,
            )
        )
    for event in note.guidance_events:
        parts.extend(
            (
                event.metric,
                event.period,
                event.value,
                event.comparator,
                event.previous_value,
                event.note,
            )
        )
    return " ".join(parts).lower()


def _has_genuine_guidance(text: str) -> bool:
    for sentence in re.split(r"(?<=[.!?;])\s+|\n+", text):
        if not _FORWARD_MARKER_RE.search(sentence):
            continue
        if (
            _MEASURABLE_RE.search(sentence)
            or _TIMEFRAME_RE.search(sentence)
            or _COMPARATIVE_GUIDANCE_RE.search(sentence)
            or _COMMITTED_ACTION_RE.search(sentence)
        ):
            return True
    return False


def _calculation_warnings(note: AnalystNote) -> Iterable[str]:
    """Block only genuinely unauditable share/control calculations.

    Phase 2 calculations such as revenue growth, EBITDA margin, NPV uplift and
    book-value discounts are percentages too, but they do not need a share-count
    denominator. Their visible numeric inputs are checked separately by the
    publication-quality layer. The stricter denominator rule belongs only to
    dilution, ownership and voting/share-count ratios.
    """

    share_ratio_terms = (
        "dilution",
        "ownership",
        "voting",
        "share count",
        "shares issued",
        "shares outstanding",
        "concert party",
    )
    share_denominator_markers = (
        "issued share capital",
        "pre-placing",
        "voting rights",
        "shares outstanding",
        "denominator",
        "total shares",
        "existing shares",
        "enlarged share capital",
        "calculated from",
    )

    for fact in note.key_facts:
        if fact.basis != "calculated":
            continue
        if not fact.note.strip():
            yield f"GUARDRAIL: Calculated fact '{fact.label}' does not show its inputs."
            continue

        descriptor = " ".join((fact.label, fact.metric)).lower()
        share_ratio = any(term in descriptor for term in share_ratio_terms)
        if share_ratio and not any(
            marker in fact.note.lower() for marker in share_denominator_markers
        ):
            yield (
                f"GUARDRAIL: Calculated share/control ratio '{fact.label}' does not "
                "identify verified inputs or a share-count denominator."
            )


def guardrail_warnings(
    announcement: AnnouncementInput,
    note: AnalystNote,
) -> list[str]:
    source = announcement.text
    output = _note_text(note)
    warnings: list[str] = []

    for label, source_pattern, required_terms in _ADVERSE_RULES:
        if source_pattern.search(source) and not any(term in output for term in required_terms):
            warnings.append(
                f"GUARDRAIL: Explicit {label} appears in the source but is absent "
                "from the analytical record."
            )

    has_guidance_event = any(
        event.status in _GUIDANCE_STATUSES for event in note.guidance_events
    )
    if (
        has_guidance_event
        and _ASPIRATION_RE.search(source)
        and not _has_genuine_guidance(source)
    ):
        warnings.append(
            "GUARDRAIL: The output classifies guidance, but the source appears "
            "to contain only unquantified or conditional management intent."
        )

    warnings.extend(_calculation_warnings(note))
    return list(dict.fromkeys(warnings))


def apply_analysis_guardrails(
    announcement: AnnouncementInput,
    note: AnalystNote,
) -> AnalystNote:
    warnings = [*note.source_warnings, *guardrail_warnings(announcement, note)]
    return note.model_copy(
        update={"source_warnings": list(dict.fromkeys(warnings))}
    )
