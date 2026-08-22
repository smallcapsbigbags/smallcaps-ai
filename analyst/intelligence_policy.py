from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from analyst.intelligence import (
    AnalystIntelligenceBundle,
    IntelligenceFinding,
    detect_analytical_tensions as _base_detect_analytical_tensions,
)
from analyst.kpi_profiles import KPIProfileSnapshot, infer_kpi_profile
from analyst.models import AnalystNote, AnnouncementInput

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")


def _normalise(value: object) -> str:
    text = " ".join(str(value or "").lower().replace("&", " and ").split())
    return " ".join(
        "".join(char if char.isalnum() else " " for char in text).split()
    )


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    normalised = _normalise(text)
    return any(_normalise(term) in normalised for term in terms)


def _organic_growth_is_unavailable(text: str) -> bool:
    """Recognise explicit non-disclosure as a gap, not an organic KPI disclosure."""

    normalised = _normalise(text)
    organic_markers = (
        "organic growth",
        "organic revenue",
        "organic performance",
        "organically",
        "like for like growth",
    )
    if not any(_normalise(marker) in normalised for marker in organic_markers):
        return True

    unavailable_markers = (
        "not disclosed",
        "not quantified",
        "not separately disclosed",
        "not separately quantified",
        "not provided",
        "not stated",
        "cannot be determined",
        "cannot be separated",
        "unable to separate",
        "no organic",
    )
    return any(_normalise(marker) in normalised for marker in unavailable_markers)


def _add_acquisition_organic_gap(
    announcement: AnnouncementInput,
    note: AnalystNote,
    findings: list[IntelligenceFinding],
) -> list[IntelligenceFinding]:
    if any(item.code == "ACQUISITION_ORGANIC_GAP" for item in findings):
        return findings

    source_text = announcement.text
    acquisition_led = _contains_any(
        source_text,
        (
            "contribution from acquisitions",
            "contributions from acquisitions",
            "acquisition contribution",
            "acquired businesses",
            "acquisition led",
            "buy and build",
        ),
    )
    if not acquisition_led or not _organic_growth_is_unavailable(source_text):
        return findings

    note_text = " ".join(
        (
            note.headline,
            note.takeaway,
            note.analyst_view,
            note.what_changed.before,
            note.what_changed.today,
            note.what_changed.read_through,
            *note.new_information,
            *note.supports_case,
            *note.challenges_case,
            *note.watch_items,
            *note.disclosure_assessment.missing_items,
        )
    )
    organic_fact = any(
        _contains_any(
            f"{fact.metric} {fact.label}",
            ("organic growth", "organic revenue", "like for like growth"),
        )
        for fact in note.key_facts
    )
    if organic_fact and not _organic_growth_is_unavailable(note_text):
        return findings

    findings.append(
        IntelligenceFinding(
            code="ACQUISITION_ORGANIC_GAP",
            title=(
                "Acquisitions contributed to growth but organic performance is unclear"
            ),
            severity="info",
            direction="unclear",
            explanation=(
                "The source attributes some growth to acquisitions without quantifying "
                "the underlying organic contribution. The note should not present all "
                "growth as like-for-like progress."
            ),
            evidence=[
                "The current RNS attributes part of growth to acquisitions and does not "
                "provide a quantified organic split."
            ],
            related_metrics=["organic growth"],
            surface_term_groups=[
                ["organic"],
                ["not disclosed", "unclear", "not quantified", "unknown"],
            ],
        )
    )
    return findings


def _explicit_funding_need(text: str) -> bool:
    return _contains_any(
        text,
        (
            "requires further funding",
            "require further funding",
            "will require further funding",
            "will require additional funding",
            "needs additional funding",
            "need additional funding",
            "funding requirement remains",
            "funding requirement has increased",
            "no binding financing",
            "financing has not been agreed",
            "funding has not been agreed",
            "insufficient working capital",
            "funding discussions are ongoing",
        ),
    )


def _explicit_funding_sufficiency(text: str) -> bool:
    return _contains_any(
        text,
        (
            "no additional funding requirement",
            "does not require additional funding",
            "will not require additional funding",
            "fully funded through",
            "funded through the next milestone",
            "cash is expected to fund",
            "cash expected to fund",
            "sufficient cash to fund",
            "funded to the next milestone",
        ),
    )


def _remove_negated_findings(
    announcement: AnnouncementInput,
    findings: list[IntelligenceFinding],
) -> list[IntelligenceFinding]:
    """Do not turn an explicit sufficiency statement into a funding warning."""

    if not _explicit_funding_sufficiency(announcement.text):
        return findings
    if _explicit_funding_need(announcement.text):
        return findings
    return [
        item for item in findings if item.code != "LIFE_SCIENCE_FUNDING_GAP"
    ]


def detect_analytical_tensions(
    announcement: AnnouncementInput,
    note: AnalystNote,
    prior_context: Sequence[Mapping[str, object]] = (),
    *,
    profile: KPIProfileSnapshot | None = None,
) -> list[IntelligenceFinding]:
    """Apply the base detector plus fail-safe wording/disclosure policies."""

    findings = list(
        _base_detect_analytical_tensions(
            announcement,
            note,
            prior_context,
            profile=profile,
        )
    )
    findings = _add_acquisition_organic_gap(announcement, note, findings)
    findings = _remove_negated_findings(announcement, findings)
    deduped: list[IntelligenceFinding] = []
    seen: set[str] = set()
    for finding in findings:
        if finding.code in seen:
            continue
        seen.add(finding.code)
        deduped.append(finding)
    deduped.sort(
        key=lambda item: (item.severity == "review", item.code),
        reverse=True,
    )
    return deduped[:8]


def _interpretive_sentences(note: AnalystNote) -> list[str]:
    """Use investor-facing interpretation, not raw KeyFact labels, as resolution proof."""

    sections = [
        note.headline,
        note.takeaway,
        note.impact_rationale,
        note.what_changed.before,
        note.what_changed.today,
        note.what_changed.read_through,
        note.analyst_view,
        *note.new_information,
        *note.reiterated_information,
        *note.supports_case,
        *note.challenges_case,
        *note.watch_items,
        *note.disclosure_assessment.missing_items,
        note.disclosure_assessment.management_language_mismatch,
        note.disclosure_assessment.note,
    ]
    output: list[str] = []
    for section in sections:
        output.extend(
            sentence.strip()
            for sentence in _SENTENCE_SPLIT_RE.split(str(section or "").strip())
            if sentence.strip()
        )
    return output


def finding_is_resolved(
    finding: IntelligenceFinding,
    note: AnalystNote,
) -> bool:
    """A finding is resolved only when the analytical relationship is explained.

    KeyFact labels alone are not enough. At least one investor-facing sentence must
    contain one term from each required group, which prevents an unrelated positive
    verb elsewhere in the note from making a debt or margin warning look resolved.
    """

    if not finding.surface_term_groups:
        return True
    normalised_groups = [
        [_normalise(term) for term in group if _normalise(term)]
        for group in finding.surface_term_groups
    ]
    normalised_groups = [group for group in normalised_groups if group]
    if not normalised_groups:
        return True

    for sentence in _interpretive_sentences(note):
        text = _normalise(sentence)
        if all(any(term in text for term in group) for group in normalised_groups):
            return True
    return False


def unresolved_intelligence_findings(
    announcement: AnnouncementInput,
    note: AnalystNote,
    prior_context: Sequence[Mapping[str, object]] = (),
) -> tuple[KPIProfileSnapshot, list[IntelligenceFinding]]:
    profile = infer_kpi_profile(announcement, prior_context)
    findings = detect_analytical_tensions(
        announcement,
        note,
        prior_context,
        profile=profile,
    )
    return profile, [
        finding for finding in findings if not finding_is_resolved(finding, note)
    ]


__all__ = [
    "AnalystIntelligenceBundle",
    "IntelligenceFinding",
    "detect_analytical_tensions",
    "finding_is_resolved",
    "unresolved_intelligence_findings",
]
