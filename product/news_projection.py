from __future__ import annotations

import re

from analyst.models import AnalystNote, AnnouncementInput, GuidanceEvent, KeyFact
from product.news_contract import (
    CompanyNewsItem,
    MarketReaction,
    MaterialFact,
    SupportedChange,
    direction_from_colour,
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _compact_headline(value: str, *, limit: int = 140) -> str:
    text = _clean(value).rstrip(". ")
    if len(text) <= limit:
        return text
    shortened = text[: limit + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return shortened or text[:limit].rstrip()


def _compact_take(note: AnalystNote, *, word_limit: int = 45) -> str:
    """Project a compact public take without asking the model for another rewrite.

    New Facts. No fluff. analyses are prompted to keep `takeaway` within 45 words.
    The fallback paths exist so older stored AnalystNotes can still be projected
    safely during migration without an extra model call.
    """

    candidates = [_clean(note.takeaway), _clean(note.analyst_view)]
    for candidate in candidates:
        if candidate and len(candidate.split()) <= word_limit:
            return candidate

    source = candidates[0] or candidates[1] or _clean(note.headline)
    if not source:
        raise ValueError("AnalystNote has no public take text")

    sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(source) if part.strip()]
    selected: list[str] = []
    count = 0
    for sentence in sentences:
        words = sentence.split()
        if selected and count + len(words) > word_limit:
            break
        if len(words) > word_limit and not selected:
            break
        selected.append(sentence)
        count += len(words)
    if selected:
        return " ".join(selected)

    words = source.split()[:word_limit]
    if not words:
        raise ValueError("AnalystNote has no public take text")
    return " ".join(words).rstrip(" ,;:-")


def _single_number(value: object) -> float | None:
    text = _clean(value)
    tokens = _NUMBER_RE.findall(text)
    if len(tokens) != 1:
        return None
    try:
        return float(tokens[0].replace(",", ""))
    except ValueError:
        return None


def _fact_change_direction(fact: KeyFact) -> str:
    if fact.information_status in {"reiterated", "previously-disclosed"}:
        return "flat"

    current = fact.value_numeric
    if current is None:
        current = _single_number(fact.value)
    previous = _single_number(fact.previous_value)
    if current is None or previous is None:
        return "unclear"
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "flat"


def _fact_change(fact: KeyFact, announcement: AnnouncementInput) -> SupportedChange | None:
    before = _clean(fact.previous_value) or _clean(fact.comparator)
    if not before:
        return None
    return SupportedChange(
        label=_clean(fact.label),
        direction=_fact_change_direction(fact),
        today=_clean(fact.value),
        before=before,
        basis="compared",
        source_id=announcement.source_id,
        comparator_source_id=_clean(fact.comparator_source_id),
        note=_clean(fact.note),
    )


def _guidance_direction(event: GuidanceEvent) -> str:
    status = event.status
    if status == "upgraded":
        return "up"
    if status in {"downgraded", "withdrawn", "missed"}:
        return "down"
    if status in {"maintained", "reiterated", "delivered"}:
        return "flat"
    if status == "issued":
        return "new"
    return "unclear"


def _guidance_change(
    event: GuidanceEvent,
    announcement: AnnouncementInput,
) -> SupportedChange | None:
    if event.status in {"not-applicable", "not-disclosed"}:
        return None

    before = _clean(event.previous_value) or _clean(event.comparator)
    today = _clean(event.value)
    if not today:
        if event.status in {"maintained", "reiterated"}:
            today = "Guidance maintained"
        elif event.status == "withdrawn":
            today = "Guidance withdrawn"
        elif event.status == "upgraded":
            today = "Guidance upgraded"
        elif event.status == "downgraded":
            today = "Guidance downgraded"
        elif event.status == "missed":
            today = "Prior guidance missed"
        elif event.status == "delivered":
            today = "Prior guidance delivered"
        elif event.status == "issued":
            today = "New guidance issued"
        else:
            today = event.status.replace("-", " ").title()

    return SupportedChange(
        label=_clean(event.metric) or "Guidance",
        direction=_guidance_direction(event),
        today=today,
        before=before,
        basis="compared" if before else "explicit-transition",
        source_id=announcement.source_id,
        comparator_source_id=_clean(event.previous_source_id),
        note=_clean(event.note),
    )


def _material_fact(fact: KeyFact, announcement: AnnouncementInput) -> MaterialFact:
    return MaterialFact(
        label=_clean(fact.label),
        value=_clean(fact.value),
        basis=fact.basis,
        source_id=announcement.source_id,
        source_url=announcement.source_url,
        note=_clean(fact.note),
    )


def _dedupe_changes(changes: list[SupportedChange]) -> list[SupportedChange]:
    output: list[SupportedChange] = []
    seen: set[tuple[str, str, str]] = set()
    for change in changes:
        key = (
            _clean(change.label).lower(),
            _clean(change.today).lower(),
            _clean(change.before).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(change)
    return output


def project_company_news(
    announcement: AnnouncementInput,
    note: AnalystNote,
    *,
    market: MarketReaction | None = None,
) -> CompanyNewsItem:
    """Deterministically project the rich AnalystNote into the compact public contract.

    This function performs no model call. It preserves every KeyFact, exposes only
    structured/supported changes, and keeps later market reaction separate from the
    point-in-time analyst judgement.
    """

    if note.source_id != announcement.source_id:
        raise ValueError("announcement and AnalystNote source_id must match")

    changes: list[SupportedChange] = []
    for fact in note.key_facts:
        change = _fact_change(fact, announcement)
        if change is not None:
            changes.append(change)
    for event in note.guidance_events:
        change = _guidance_change(event, announcement)
        if change is not None:
            changes.append(change)

    # The rich WhatChanged field remains useful as a final fallback when company
    # history is established but the delta was not representable in a structured
    # KPI/guidance field. Building coverage never creates a synthetic comparison.
    if not changes and note.what_changed.coverage_status == "established":
        before = _clean(note.what_changed.before)
        today = _clean(note.what_changed.today)
        if before and today and "coverage" not in before.lower():
            changes.append(
                SupportedChange(
                    label="Main change",
                    direction="unclear",
                    today=today,
                    before=before,
                    basis="compared",
                    source_id=announcement.source_id,
                )
            )

    source_url = announcement.source_url
    if not source_url and announcement.source_urls:
        source_url = announcement.source_urls[0]

    return CompanyNewsItem(
        source_id=announcement.source_id,
        ticker=announcement.ticker,
        company=announcement.company,
        published_at=announcement.published_at,
        news_type=note.rns_type,
        direction=direction_from_colour(note.impact_colour),
        materiality=note.impact_score,
        headline=_compact_headline(note.headline),
        take=_compact_take(note),
        material_facts=[_material_fact(fact, announcement) for fact in note.key_facts],
        changes=_dedupe_changes(changes),
        baseline_status=note.what_changed.coverage_status,
        watch_next=[_clean(item) for item in note.watch_items[:3] if _clean(item)],
        source_url=source_url,
        market=market,
    )
