from __future__ import annotations

import re
from typing import Literal

from analyst.models import AnalystNote, KeyFact, QualityFlag, QualityReport

MonitoringSignal = Literal["GREEN", "AMBER", "RED", "NO COLOUR"]
MonitoringOutlook = Literal[
    "UPGRADED",
    "MAINTAINED",
    "DOWNGRADED",
    "NEW GUIDANCE",
    "MIXED",
    "N/A",
]

_SIGNAL_LABELS: dict[str, MonitoringSignal] = {
    "green": "GREEN",
    "amber": "AMBER",
    "red": "RED",
    "grey": "NO COLOUR",
}

_BALANCE_SHEET_TERMS = (
    "net debt",
    "net cash",
    "cash balance",
    "cash",
    "gross debt",
    "liquidity",
    "working capital",
    "funding runway",
    "cash runway",
    "covenant headroom",
)

_BALANCE_SHEET_PRIORITY = {
    "net debt": 0,
    "net cash": 1,
    "liquidity": 2,
    "cash balance": 3,
    "cash": 4,
    "gross debt": 5,
    "covenant headroom": 6,
    "working capital": 7,
    "funding runway": 8,
    "cash runway": 9,
}

_SUMMARY_OPENING_RE = re.compile(
    r"^(?:the company|management|the board)\s+"
    r"(?:announced|reports?|reported|says?|said|confirmed|has announced|has reported)\b",
    re.IGNORECASE,
)
_GENERIC_CHANGE_VALUES = {
    "",
    "coverage is building",
    "coverage is building.",
    "no comparator available",
    "no meaningful comparator",
    "not disclosed",
    "n/a",
    "unknown",
}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w£$€%.-]+\b", text))


def monitoring_signal(note: AnalystNote) -> MonitoringSignal:
    """Translate the internal direction token into the monitoring-sheet label."""

    return _SIGNAL_LABELS.get(note.impact_colour, "NO COLOUR")


def monitoring_outlook(note: AnalystNote) -> MonitoringOutlook:
    """Derive the compact public outlook state from genuine guidance events."""

    statuses = {event.status for event in note.guidance_events}
    favourable = bool(statuses & {"upgraded"})
    adverse = bool(statuses & {"downgraded", "withdrawn", "missed"})

    if favourable and adverse:
        return "MIXED"
    if adverse:
        return "DOWNGRADED"
    if favourable:
        return "UPGRADED"
    if statuses & {"issued"}:
        return "NEW GUIDANCE"
    if statuses & {"maintained", "reiterated"}:
        return "MAINTAINED"
    return "N/A"


def _balance_sheet_rank(fact: KeyFact) -> tuple[int, int, int]:
    text = f"{fact.metric} {fact.label}".strip().lower()
    priority = min(
        (
            rank
            for term, rank in _BALANCE_SHEET_PRIORITY.items()
            if term in text
        ),
        default=99,
    )
    information_rank = {
        "new": 0,
        "reiterated": 1,
        "previously-disclosed": 2,
        "not-disclosed": 3,
    }.get(fact.information_status, 4)
    basis_rank = {
        "reported": 0,
        "calculated": 1,
        "not-disclosed": 2,
        "source-warning": 3,
    }.get(fact.basis, 4)
    return (information_rank, priority, basis_rank)


def is_balance_sheet_fact(fact: KeyFact) -> bool:
    text = f"{fact.metric} {fact.label}".strip().lower()
    return any(term in text for term in _BALANCE_SHEET_TERMS)


def monitoring_balance_sheet_fact(note: AnalystNote) -> KeyFact | None:
    """Return the most useful balance-sheet fact disclosed in this Analyst Note."""

    candidates = [fact for fact in note.key_facts if is_balance_sheet_fact(fact)]
    return min(candidates, key=_balance_sheet_rank) if candidates else None


def balance_sheet_is_carried(fact: KeyFact) -> bool:
    """Identify context that came from an earlier disclosure, not today's RNS."""

    return fact.information_status in {"reiterated", "previously-disclosed"}


def monitoring_contract_flags(note: AnalystNote) -> list[QualityFlag]:
    """Apply the SmallcapsBigBags monitoring-sheet editorial gate.

    This contract is intentionally stricter than the general research-note ceiling.
    New analyses that need editorial rescue are routed to owner review rather than
    being published with a long or summary-style AI View.
    """

    flags: list[QualityFlag] = []

    view_words = _word_count(note.analyst_view)
    if view_words > 50:
        flags.append(
            QualityFlag(
                code="SCBB_AI_VIEW_LENGTH",
                severity="review",
                message=(
                    f"AI View is {view_words} words; the monitoring-sheet contract "
                    "has a hard maximum of 50 words."
                ),
            )
        )
    elif view_words > 45:
        flags.append(
            QualityFlag(
                code="SCBB_AI_VIEW_LENGTH",
                severity="info",
                message=(
                    f"AI View is {view_words} words; it is close to the 50-word limit."
                ),
            )
        )

    if _SUMMARY_OPENING_RE.search(note.analyst_view.strip()):
        flags.append(
            QualityFlag(
                code="SCBB_AI_VIEW_SUMMARY_OPENING",
                severity="info",
                message=(
                    "AI View opens by re-summarising management's announcement; "
                    "lead with the analyst judgement instead."
                ),
            )
        )

    changed = " ".join(note.what_changed.today.strip().split())
    changed_words = _word_count(changed)
    if changed.lower() in _GENERIC_CHANGE_VALUES:
        flags.append(
            QualityFlag(
                code="SCBB_WHAT_CHANGED_MISSING",
                severity="review",
                message=(
                    "What Changed must state today's decision-useful delta; "
                    "coverage-building language belongs in the before field."
                ),
            )
        )
    elif changed_words > 55:
        flags.append(
            QualityFlag(
                code="SCBB_WHAT_CHANGED_LENGTH",
                severity="review",
                message=(
                    f"What Changed is {changed_words} words; compress it to one "
                    "self-contained monitoring-sheet delta."
                ),
            )
        )
    elif changed_words > 40:
        flags.append(
            QualityFlag(
                code="SCBB_WHAT_CHANGED_LENGTH",
                severity="info",
                message=(
                    f"What Changed is {changed_words} words; consider tightening it "
                    "for the monitoring sheet."
                ),
            )
        )

    has_balance_sheet_driver = any(
        driver.dimension == "balance-sheet" for driver in note.impact_drivers
    )
    balance_fact = monitoring_balance_sheet_fact(note)
    if has_balance_sheet_driver and balance_fact is None:
        flags.append(
            QualityFlag(
                code="SCBB_BALANCE_SHEET_FACT_MISSING",
                severity="review",
                message=(
                    "Balance-sheet impact is claimed but no cash, debt, liquidity, "
                    "working-capital or runway fact is retained."
                ),
            )
        )
    elif balance_fact is not None and balance_sheet_is_carried(balance_fact):
        if not (balance_fact.as_of_date.strip() or balance_fact.period.strip()):
            flags.append(
                QualityFlag(
                    code="SCBB_CARRIED_BALANCE_SHEET_DATE",
                    severity="info",
                    message=(
                        "Carried-forward balance-sheet context should retain the "
                        "reporting date or period."
                    ),
                )
            )

    return flags


def merge_monitoring_quality(
    report: QualityReport,
    note: AnalystNote,
) -> QualityReport:
    """Merge monitoring-sheet flags into the existing publication-safety report."""

    flags = [*report.flags, *monitoring_contract_flags(note)]
    deduped: list[QualityFlag] = []
    seen: set[tuple[str, str]] = set()
    for flag in flags:
        key = (flag.code, flag.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(flag)

    if any(flag.severity == "block" for flag in deduped):
        status = "blocked"
    elif any(flag.severity == "review" for flag in deduped):
        status = "review"
    else:
        status = "publishable"

    return QualityReport(status=status, flags=deduped)
