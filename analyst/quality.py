from __future__ import annotations

import re
from collections.abc import Sequence

from analyst.intelligence_policy import unresolved_intelligence_findings
from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    QualityFlag,
    QualityReport,
    QualityStatus,
)

_PLAIN_ENGLISH_TERMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("legalese 'pursuant to'", re.compile(r"\bpursuant to\b", re.IGNORECASE)),
    ("legalese 'in respect of'", re.compile(r"\bin respect of\b", re.IGNORECASE)),
    ("legalese 'therein'", re.compile(r"\btherein\b", re.IGNORECASE)),
    ("legalese 'aforementioned'", re.compile(r"\baforementioned\b", re.IGNORECASE)),
    ("analyst jargon 'read-through'", re.compile(r"\bread[- ]through\b", re.IGNORECASE)),
    ("analyst jargon 'incremental'", re.compile(r"\bincremental\b", re.IGNORECASE)),
    ("analyst jargon 'directional'", re.compile(r"\bdirectional\b", re.IGNORECASE)),
    ("analyst jargon 'trajectory'", re.compile(r"\btrajectory\b", re.IGNORECASE)),
    ("analyst jargon 'visibility'", re.compile(r"\bvisibility\b", re.IGNORECASE)),
    ("analyst jargon 'accretive'", re.compile(r"\baccretive\b", re.IGNORECASE)),
    ("PR phrase 'significant milestone'", re.compile(r"\bsignificant milestone\b", re.IGNORECASE)),
    ("PR phrase 'well positioned'", re.compile(r"\bwell positioned\b", re.IGNORECASE)),
    ("PR phrase 'underscores'", re.compile(r"\bunderscores\b", re.IGNORECASE)),
    ("PR phrase 'robust'", re.compile(r"\brobust\b", re.IGNORECASE)),
    ("PR phrase 'transformational'", re.compile(r"\btransformational\b", re.IGNORECASE)),
)
_RULE_9_RE = re.compile(r"\bRule\s*9\b", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _status(flags: list[QualityFlag]) -> QualityStatus:
    if any(flag.severity == "block" for flag in flags):
        return "blocked"
    if any(flag.severity == "review" for flag in flags):
        return "review"
    return "publishable"


def _public_prose(note: AnalystNote) -> list[tuple[str, str]]:
    return [
        ("headline", note.headline),
        ("takeaway", note.takeaway),
        ("impact rationale", note.impact_rationale),
        ("what changed — before", note.what_changed.before),
        ("what changed — today", note.what_changed.today),
        ("what changed — why it matters", note.what_changed.read_through),
        ("Smallcaps.ai view", note.analyst_view),
        *[("supports case", value) for value in note.supports_case],
        *[("challenges case", value) for value in note.challenges_case],
        *[("what to watch", value) for value in note.watch_items],
    ]


def _plain_english_flags(
    announcement: AnnouncementInput,
    note: AnalystNote,
) -> list[QualityFlag]:
    flags: list[QualityFlag] = []
    prose = _public_prose(note)

    for section, text in prose:
        for label, pattern in _PLAIN_ENGLISH_TERMS:
            if pattern.search(text):
                flags.append(
                    QualityFlag(
                        code="PLAIN_ENGLISH_JARGON",
                        severity="info",
                        message=f"{section} contains {label}; simplify if it is not essential.",
                    )
                )

    long_sentences: list[tuple[str, int]] = []
    for section, text in prose:
        for sentence in _SENTENCE_SPLIT_RE.split(text.strip()):
            words = re.findall(r"\b[\w£$€%.-]+\b", sentence)
            if len(words) > 38:
                long_sentences.append((section, len(words)))
    if len(long_sentences) >= 2:
        flags.append(
            QualityFlag(
                code="PLAIN_ENGLISH_LENGTH",
                severity="review",
                message=(
                    "Public analysis contains multiple sentences over 38 words; "
                    "rewrite for a normal investor."
                ),
            )
        )
    elif long_sentences:
        section, count = long_sentences[0]
        flags.append(
            QualityFlag(
                code="PLAIN_ENGLISH_LENGTH",
                severity="info",
                message=f"{section} contains a {count}-word sentence; consider simplifying it.",
            )
        )

    if len(note.headline.split()) > 20:
        flags.append(
            QualityFlag(
                code="HEADLINE_TOO_LONG",
                severity="review",
                message="Headline is over 20 words and should state the main change more directly.",
            )
        )
    if len(note.takeaway.split()) > 120:
        flags.append(
            QualityFlag(
                code="TAKEAWAY_TOO_LONG",
                severity="review",
                message="Takeaway is over 120 words; compress it to what happened and why it matters.",
            )
        )
    if len(note.analyst_view.split()) > 180:
        flags.append(
            QualityFlag(
                code="ANALYST_VIEW_TOO_LONG",
                severity="review",
                message="Smallcaps.ai view is over 180 words and should be more decision-useful.",
            )
        )

    if _RULE_9_RE.search(announcement.text):
        explained = any(
            _RULE_9_RE.search(item.term)
            for item in note.disclosure_assessment.concept_explanations
        )
        if not explained:
            flags.append(
                QualityFlag(
                    code="UNEXPLAINED_RULE_9",
                    severity="review",
                    message="Rule 9 is material to the source but is not explained in plain English.",
                )
            )

    for fact in note.key_facts:
        if fact.basis == "calculated":
            numeric_tokens = re.findall(
                r"(?:£|\$|€)?\d+(?:\.\d+)?(?:%|m|bn)?",
                fact.note,
                re.IGNORECASE,
            )
            if len(numeric_tokens) < 2:
                flags.append(
                    QualityFlag(
                        code="CALCULATION_INPUTS_UNCLEAR",
                        severity="review",
                        message=(
                            f"Calculated fact '{fact.label}' does not make at least two "
                            "numeric inputs visible in its calculation note."
                        ),
                    )
                )

    return flags


def _intelligence_flags(
    announcement: AnnouncementInput,
    note: AnalystNote,
    prior_context: Sequence[dict[str, object]],
) -> list[QualityFlag]:
    profile, unresolved = unresolved_intelligence_findings(
        announcement,
        note,
        prior_context,
    )
    flags: list[QualityFlag] = []
    for finding in unresolved:
        severity = "review" if finding.severity == "review" else "info"
        evidence = " ".join(finding.evidence[:2]).strip()
        profile_copy = (
            f" Inferred profile: {profile.label} ({profile.confidence:.0%} confidence)."
            if profile.profile_id != "generic"
            else ""
        )
        flags.append(
            QualityFlag(
                code=f"INTELLIGENCE_{finding.code}",
                severity=severity,
                message=(
                    f"{finding.title}. {finding.explanation}"
                    + (f" Evidence: {evidence}" if evidence else "")
                    + profile_copy
                ),
            )
        )
    return flags


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

    if note.what_changed.coverage_status == "established" and not prior_context:
        flags.append(
            QualityFlag(
                code="UNSUPPORTED_ESTABLISHED_COVERAGE",
                severity="block",
                message="What Changed claims established history but no prior context was supplied.",
            )
        )

    if announcement.evidence_status != "metadata-only" and not note.source_references:
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

    flags.extend(_intelligence_flags(announcement, note, prior_context))
    flags.extend(_plain_english_flags(announcement, note))

    deduped: list[QualityFlag] = []
    seen: set[tuple[str, str]] = set()
    for flag in flags:
        key = (flag.code, flag.message)
        if key not in seen:
            seen.add(key)
            deduped.append(flag)

    return QualityReport(status=_status(deduped), flags=deduped)
