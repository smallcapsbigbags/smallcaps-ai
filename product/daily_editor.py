from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from analyst.monitoring_sheet import MonitoringOutlook, MonitoringSignal

DAILY_EDITOR_SCHEMA_VERSION = "aim-daily-editor-v1"
DAILY_EDITOR_VERSION = "aim-daily-editor-1.0"
DEFAULT_EDITOR_CUTOFF = time(12, 0)

DailyEditorBucket = Literal["lead", "also_matters", "quick_take"]

_IMPACT_POINTS = {1: 5, 2: 15, 3: 30, 4: 40, 5: 50}
_RNS_TYPE_BONUS = {
    "Funding & solvency": 28,
    "Takeover": 26,
    "Fundraising": 16,
    "Results & trading": 14,
    "Acquisition": 14,
    "Disposal": 13,
    "Operations": 10,
    "Contracts": 8,
    "Listing status": 8,
    "Partnerships": 5,
    "Board & advisers": 3,
    "Remuneration": 2,
    "Director dealing": 2,
    "Corporate": 1,
    "Holdings": 0,
    "Share capital": 0,
    "Other": 0,
}
_OUTLOOK_BONUS = {
    "DOWNGRADED": 18,
    "UPGRADED": 14,
    "MIXED": 10,
    "NEW GUIDANCE": 10,
    "MAINTAINED": 2,
    "N/A": 0,
}
_SIGNAL_BONUS = {
    "RED": 4,
    "GREEN": 3,
    "AMBER": 1,
    "NO COLOUR": 0,
}
_TITLE_BONUSES: tuple[tuple[str, int, str], ...] = (
    ("profit warning", 20, "Explicit profit warning."),
    ("strategic review", 18, "Strategic review can change ownership or capital allocation."),
    ("going concern", 18, "Going-concern language is balance-sheet critical."),
    ("administrat", 20, "Administration event is investment-case critical."),
    ("covenant", 14, "Covenant event can change solvency risk."),
)

_LEAD_MIN_SCORE = 58
_ALSO_MIN_SCORE = 40
_QUICK_MIN_SCORE = 22
_MAX_ALSO = 5
_MAX_QUICK = 8


class DailyEditorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DailyEditorCandidate(DailyEditorModel):
    """Publication-safe FULL analysis projected into the newsroom ranking layer."""

    source_id: str
    ticker: str
    company: str
    published_at: datetime
    rns_title: str
    rns_type: str
    impact_score: int = Field(ge=1, le=5)
    impact_level: Literal["low", "medium", "high", "critical"]
    signal: MonitoringSignal
    outlook: MonitoringOutlook
    verdict: str
    what_changed: str
    analyst_view: str
    source_url: str
    analysis_version: str
    prompt_version: str
    model_version: str
    guidance_statuses: list[str] = Field(default_factory=list)


class DailyEditorStory(DailyEditorModel):
    primary_source_id: str
    source_ids: list[str]
    ticker: str
    company: str
    published_at: datetime
    bucket: DailyEditorBucket
    priority_score: int = Field(ge=0)
    ranking_reasons: list[str] = Field(default_factory=list)
    rns_types: list[str] = Field(default_factory=list)
    signal: MonitoringSignal
    outlook: MonitoringOutlook
    impact_score: int = Field(ge=1, le=5)
    editorial_headline: str
    why_it_matters: str
    what_changed: str
    source_urls: list[str] = Field(default_factory=list)


class DailyEditorPage(DailyEditorModel):
    schema_version: Literal["aim-daily-editor-v1"] = DAILY_EDITOR_SCHEMA_VERSION
    editor_version: Literal["aim-daily-editor-1.0"] = DAILY_EDITOR_VERSION
    generated_at: datetime
    date: str
    cutoff: str
    quiet_morning: bool
    candidate_count: int = Field(ge=0)
    published_story_count: int = Field(ge=0)
    other_analysed_count: int = Field(ge=0)
    lead: DailyEditorStory | None = None
    also_matters: list[DailyEditorStory] = Field(default_factory=list)
    quick_takes: list[DailyEditorStory] = Field(default_factory=list)


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def editorial_priority(candidate: DailyEditorCandidate) -> tuple[int, list[str]]:
    """Score attention deterministically from already validated analyst outputs.

    Pass 7 does not ask another model to rank the market. Impact, event class,
    guidance direction and a handful of high-stakes title triggers determine the
    ordering. This makes the editor explainable, cheap and benchmarkable.
    """

    score = _IMPACT_POINTS[candidate.impact_score]
    reasons = [f"Impact {candidate.impact_score}/5 contributes {score} points."]

    event_bonus = _RNS_TYPE_BONUS.get(candidate.rns_type, 0)
    if event_bonus:
        score += event_bonus
        reasons.append(
            f"{candidate.rns_type} event class contributes {event_bonus} points."
        )

    outlook_bonus = _OUTLOOK_BONUS.get(str(candidate.outlook), 0)
    if outlook_bonus:
        score += outlook_bonus
        reasons.append(
            f"Outlook {candidate.outlook} contributes {outlook_bonus} points."
        )

    signal_bonus = _SIGNAL_BONUS.get(str(candidate.signal), 0)
    if signal_bonus:
        score += signal_bonus
        reasons.append(
            f"Signal {candidate.signal} contributes {signal_bonus} tie-break points."
        )

    title = _clean(candidate.rns_title).lower()
    for marker, bonus, reason in _TITLE_BONUSES:
        if marker in title:
            score += bonus
            reasons.append(f"{reason} +{bonus} points.")
            break

    return score, reasons


def _story_for_company(candidates: list[DailyEditorCandidate]) -> DailyEditorStory:
    ranked = sorted(
        candidates,
        key=lambda item: (
            editorial_priority(item)[0],
            item.impact_score,
            item.published_at,
            item.source_id,
        ),
        reverse=True,
    )
    primary = ranked[0]
    score, reasons = editorial_priority(primary)
    source_ids = [primary.source_id]
    source_urls: list[str] = []
    rns_types: list[str] = []

    for item in ranked:
        if item.source_id not in source_ids:
            source_ids.append(item.source_id)
        source_url = _clean(item.source_url)
        if source_url and source_url not in source_urls:
            source_urls.append(source_url)
        rns_type = _clean(item.rns_type) or "Other"
        if rns_type not in rns_types:
            rns_types.append(rns_type)

    if len(ranked) > 1:
        reasons.append(
            f"{len(ranked)} FULL announcements for {primary.ticker} are consolidated into one company story."
        )

    return DailyEditorStory(
        primary_source_id=primary.source_id,
        source_ids=source_ids,
        ticker=primary.ticker,
        company=primary.company,
        published_at=primary.published_at,
        bucket="quick_take",
        priority_score=score,
        ranking_reasons=reasons,
        rns_types=rns_types,
        signal=primary.signal,
        outlook=primary.outlook,
        impact_score=primary.impact_score,
        editorial_headline=_clean(primary.verdict) or _clean(primary.rns_title),
        why_it_matters=_clean(primary.analyst_view) or _clean(primary.what_changed),
        what_changed=_clean(primary.what_changed),
        source_urls=source_urls,
    )


def build_daily_editor(
    *,
    day: date,
    cutoff: time,
    candidates: list[DailyEditorCandidate],
    generated_at: datetime | None = None,
) -> DailyEditorPage:
    grouped: dict[str, list[DailyEditorCandidate]] = defaultdict(list)
    for candidate in candidates:
        ticker = _clean(candidate.ticker).upper()
        if not ticker:
            continue
        grouped[ticker].append(candidate)

    stories = [_story_for_company(items) for items in grouped.values()]
    stories.sort(
        key=lambda item: (
            item.priority_score,
            item.impact_score,
            item.published_at,
            item.primary_source_id,
        ),
        reverse=True,
    )

    lead: DailyEditorStory | None = None
    also: list[DailyEditorStory] = []
    quick: list[DailyEditorStory] = []
    start_index = 0

    if stories and stories[0].priority_score >= _LEAD_MIN_SCORE:
        lead = stories[0].model_copy(update={"bucket": "lead"})
        start_index = 1

    for story in stories[start_index:]:
        if story.priority_score >= _ALSO_MIN_SCORE and len(also) < _MAX_ALSO:
            also.append(story.model_copy(update={"bucket": "also_matters"}))
            continue
        if story.priority_score >= _QUICK_MIN_SCORE and len(quick) < _MAX_QUICK:
            quick.append(story.model_copy(update={"bucket": "quick_take"}))

    surfaced_source_ids: set[str] = set()
    if lead is not None:
        surfaced_source_ids.update(lead.source_ids)
    for story in [*also, *quick]:
        surfaced_source_ids.update(story.source_ids)

    candidate_ids = {candidate.source_id for candidate in candidates}
    published_story_count = (1 if lead is not None else 0) + len(also) + len(quick)
    generated = generated_at or datetime.now(timezone.utc)

    return DailyEditorPage(
        generated_at=generated,
        date=day.isoformat(),
        cutoff=cutoff.strftime("%H:%M"),
        quiet_morning=lead is None,
        candidate_count=len(candidate_ids),
        published_story_count=published_story_count,
        other_analysed_count=max(0, len(candidate_ids - surfaced_source_ids)),
        lead=lead,
        also_matters=also,
        quick_takes=quick,
    )
