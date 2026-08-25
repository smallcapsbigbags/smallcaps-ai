from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from analyst.monitoring_sheet import MonitoringOutlook, MonitoringSignal

DAILY_EDITOR_SCHEMA_VERSION = "aim-daily-editor-v2"
DAILY_EDITOR_VERSION = "aim-daily-editor-2.0"

EditionState = Literal["early_read", "morning_note", "aim_close", "custom"]
CanonicalEditionState = Literal["early_read", "morning_note", "aim_close"]
DailyEditorBucket = Literal["lead", "also_matters", "quick_take"]
AlgorithmicBucket = Literal["lead", "also_matters", "quick_take", "suppressed"]
EditorialOverrideAction = Literal["lead", "promote", "demote", "suppress", "group"]
TransitionStatus = Literal["new", "promoted", "demoted", "unchanged", "dropped"]

CANONICAL_EDITION_CUTOFFS: dict[CanonicalEditionState, time] = {
    "early_read": time(7, 30),
    "morning_note": time(8, 0),
    "aim_close": time(16, 35),
}
DEFAULT_EDITOR_STATE: CanonicalEditionState = "morning_note"
DEFAULT_EDITOR_CUTOFF = CANONICAL_EDITION_CUTOFFS[DEFAULT_EDITOR_STATE]

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

_STORY_WINDOW_DAYS = {
    "takeover": 45,
    "strategic": 45,
    "solvency": 21,
    "funding": 21,
    "m_and_a": 21,
    "regulatory": 14,
    "commercial": 7,
    "operational": 7,
    "trading": 3,
    "management": 3,
    "capital": 1,
    "other": 1,
}


class DailyEditorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DailyEditorOverride(DailyEditorModel):
    source_id: str
    action: EditorialOverrideAction
    target_source_id: str = ""
    reason: str = ""
    algorithm_score: int = Field(default=0, ge=0)
    algorithm_bucket: AlgorithmicBucket = "suppressed"
    algorithm_story_key: str = ""
    created_at: datetime | None = None


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
    story_key: str = ""
    story_family: str = ""


class DailyEditorStory(DailyEditorModel):
    story_key: str
    story_family: str
    primary_source_id: str
    latest_source_id: str
    source_ids: list[str]
    ticker: str
    company: str
    first_published_at: datetime
    published_at: datetime
    bucket: DailyEditorBucket
    algorithmic_bucket: AlgorithmicBucket
    priority_score: int = Field(ge=0)
    ranking_reasons: list[str] = Field(default_factory=list)
    override_actions: list[EditorialOverrideAction] = Field(default_factory=list)
    rns_types: list[str] = Field(default_factory=list)
    signal: MonitoringSignal
    outlook: MonitoringOutlook
    impact_score: int = Field(ge=1, le=5)
    editorial_headline: str
    why_it_matters: str
    what_changed: str
    source_urls: list[str] = Field(default_factory=list)
    is_developing: bool = False


class DailyEditorPage(DailyEditorModel):
    schema_version: Literal["aim-daily-editor-v2"] = DAILY_EDITOR_SCHEMA_VERSION
    editor_version: Literal["aim-daily-editor-2.0"] = DAILY_EDITOR_VERSION
    generated_at: datetime
    date: str
    edition_state: EditionState
    cutoff: str
    quiet_morning: bool
    candidate_count: int = Field(ge=0)
    published_story_count: int = Field(ge=0)
    other_analysed_count: int = Field(ge=0)
    developing_story_count: int = Field(ge=0)
    override_count: int = Field(ge=0)
    lead: DailyEditorStory | None = None
    also_matters: list[DailyEditorStory] = Field(default_factory=list)
    quick_takes: list[DailyEditorStory] = Field(default_factory=list)


class DailyEditorTransition(DailyEditorModel):
    story_key: str
    ticker: str
    from_state: CanonicalEditionState
    to_state: CanonicalEditionState
    from_bucket: AlgorithmicBucket
    to_bucket: AlgorithmicBucket
    status: TransitionStatus


class DailyEditorTimeline(DailyEditorModel):
    schema_version: Literal["aim-daily-editor-v2"] = DAILY_EDITOR_SCHEMA_VERSION
    editor_version: Literal["aim-daily-editor-2.0"] = DAILY_EDITOR_VERSION
    generated_at: datetime
    date: str
    editions: list[DailyEditorPage] = Field(default_factory=list)
    transitions: list[DailyEditorTransition] = Field(default_factory=list)


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def resolve_editor_cutoff(
    *,
    edition_state: str | None = None,
    cutoff: time | None = None,
) -> tuple[EditionState, time]:
    state = _clean(edition_state).lower()
    if state and cutoff is not None:
        raise ValueError("edition_state cannot be combined with cutoff")
    if state:
        if state not in CANONICAL_EDITION_CUTOFFS:
            raise ValueError("edition_state must be early_read, morning_note or aim_close")
        return state, CANONICAL_EDITION_CUTOFFS[state]  # type: ignore[index,return-value]
    if cutoff is None:
        return DEFAULT_EDITOR_STATE, DEFAULT_EDITOR_CUTOFF
    if cutoff == time.min:
        raise ValueError("cutoff must be after 00:00 Europe/London")
    for canonical, canonical_cutoff in CANONICAL_EDITION_CUTOFFS.items():
        if cutoff == canonical_cutoff:
            return canonical, cutoff
    return "custom", cutoff


def editorial_story_family(rns_type: object, title: object) -> str:
    clean_type = _clean(rns_type)
    clean_title = _clean(title).lower()
    if any(marker in clean_title for marker in ("possible offer", "rule 2.6", "takeover", "offeror")):
        return "takeover"
    if "strategic review" in clean_title:
        return "strategic"
    if any(marker in clean_title for marker in ("administrat", "going concern", "covenant", "winding up")):
        return "solvency"
    if any(marker in clean_title for marker in ("placing", "fundrais", "subscription")):
        return "funding"
    mapping = {
        "Funding & solvency": "solvency",
        "Takeover": "takeover",
        "Fundraising": "funding",
        "Results & trading": "trading",
        "Acquisition": "m_and_a",
        "Disposal": "m_and_a",
        "Operations": "operational",
        "Contracts": "commercial",
        "Partnerships": "commercial",
        "Board & advisers": "management",
        "Remuneration": "management",
        "Director dealing": "management",
        "Listing status": "capital",
        "Share capital": "capital",
        "Holdings": "capital",
    }
    return mapping.get(clean_type, "other")


def story_family_window_days(family: object) -> int:
    return _STORY_WINDOW_DAYS.get(_clean(family).lower(), 1)


def make_story_key(ticker: object, family: object, anchor_source_id: object) -> str:
    clean_ticker = _clean(ticker).upper() or "UNKNOWN"
    clean_family = _clean(family).lower() or "other"
    clean_source = _clean(anchor_source_id) or "unknown"
    return f"{clean_ticker}:{clean_family}:{clean_source}"[:220]


def editorial_priority(candidate: DailyEditorCandidate) -> tuple[int, list[str]]:
    """Score attention deterministically from already validated analyst outputs."""

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


def algorithmic_bucket_for_score(score: int) -> AlgorithmicBucket:
    if score >= _LEAD_MIN_SCORE:
        return "lead"
    if score >= _ALSO_MIN_SCORE:
        return "also_matters"
    if score >= _QUICK_MIN_SCORE:
        return "quick_take"
    return "suppressed"


def promoted_bucket(bucket: AlgorithmicBucket) -> AlgorithmicBucket:
    return {
        "suppressed": "quick_take",
        "quick_take": "also_matters",
        "also_matters": "lead",
        "lead": "lead",
    }[bucket]  # type: ignore[return-value]


def demoted_bucket(bucket: AlgorithmicBucket) -> AlgorithmicBucket:
    return {
        "lead": "also_matters",
        "also_matters": "quick_take",
        "quick_take": "suppressed",
        "suppressed": "suppressed",
    }[bucket]  # type: ignore[return-value]


def _story_for_group(
    candidates: list[DailyEditorCandidate],
    *,
    story_key: str,
) -> DailyEditorStory:
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
    latest = max(ranked, key=lambda item: (item.published_at, item.source_id))
    earliest = min(ranked, key=lambda item: (item.published_at, item.source_id))
    score, reasons = editorial_priority(primary)
    source_ids: list[str] = []
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
            f"{len(ranked)} FULL announcements are consolidated into one developing story."
        )

    family = _clean(primary.story_family) or editorial_story_family(
        primary.rns_type, primary.rns_title
    )
    return DailyEditorStory(
        story_key=story_key,
        story_family=family,
        primary_source_id=primary.source_id,
        latest_source_id=latest.source_id,
        source_ids=source_ids,
        ticker=primary.ticker,
        company=primary.company,
        first_published_at=earliest.published_at,
        published_at=primary.published_at,
        bucket="quick_take",
        algorithmic_bucket=algorithmic_bucket_for_score(score),
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
        is_developing=len(source_ids) > 1,
    )


def _fallback_story_key(candidate: DailyEditorCandidate, day: date) -> str:
    family = _clean(candidate.story_family) or editorial_story_family(
        candidate.rns_type, candidate.rns_title
    )
    return f"{_clean(candidate.ticker).upper()}:{family}:{day.isoformat()}"


def _story_list(page: DailyEditorPage) -> list[DailyEditorStory]:
    return [
        *([page.lead] if page.lead is not None else []),
        *page.also_matters,
        *page.quick_takes,
    ]


def build_daily_editor(
    *,
    day: date,
    candidates: list[DailyEditorCandidate],
    cutoff: time | None = None,
    edition_state: str | None = None,
    overrides: list[DailyEditorOverride] | None = None,
    generated_at: datetime | None = None,
) -> DailyEditorPage:
    resolved_state, resolved_cutoff = resolve_editor_cutoff(
        edition_state=edition_state,
        cutoff=cutoff,
    )
    active_overrides = list(overrides or [])
    valid_candidates = [candidate for candidate in candidates if _clean(candidate.ticker)]
    candidates_by_source = {candidate.source_id: candidate for candidate in valid_candidates}
    group_keys = {
        candidate.source_id: (_clean(candidate.story_key) or _fallback_story_key(candidate, day))
        for candidate in valid_candidates
    }

    for override in active_overrides:
        if override.action != "group":
            continue
        if override.source_id in group_keys and override.target_source_id in group_keys:
            group_keys[override.source_id] = group_keys[override.target_source_id]

    grouped: dict[str, list[DailyEditorCandidate]] = defaultdict(list)
    for candidate in valid_candidates:
        grouped[group_keys[candidate.source_id]].append(candidate)

    stories = [
        _story_for_group(items, story_key=story_key)
        for story_key, items in grouped.items()
    ]
    stories.sort(
        key=lambda item: (
            item.priority_score,
            item.impact_score,
            item.published_at,
            item.primary_source_id,
        ),
        reverse=True,
    )

    desired: dict[str, AlgorithmicBucket] = {
        story.story_key: story.algorithmic_bucket for story in stories
    }
    forced_leads: set[str] = set()
    applied_actions: dict[str, list[EditorialOverrideAction]] = defaultdict(list)

    for story in stories:
        matching = [
            override
            for override in active_overrides
            if override.source_id in story.source_ids
        ]
        matching.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc))
        for override in matching:
            if override.action not in applied_actions[story.story_key]:
                applied_actions[story.story_key].append(override.action)
            if override.action == "lead":
                desired[story.story_key] = "lead"
                forced_leads.add(story.story_key)
            elif override.action == "promote":
                desired[story.story_key] = promoted_bucket(desired[story.story_key])
            elif override.action == "demote":
                desired[story.story_key] = demoted_bucket(desired[story.story_key])
            elif override.action == "suppress":
                desired[story.story_key] = "suppressed"

    decorated = [
        story.model_copy(update={"override_actions": applied_actions.get(story.story_key, [])})
        for story in stories
    ]

    lead: DailyEditorStory | None = None
    if forced_leads:
        forced = [story for story in decorated if story.story_key in forced_leads]
        if forced:
            chosen = max(
                forced,
                key=lambda item: (
                    item.priority_score,
                    item.published_at,
                    item.primary_source_id,
                ),
            )
            lead = chosen.model_copy(update={"bucket": "lead"})
    else:
        eligible_leads = [
            story for story in decorated if desired[story.story_key] == "lead"
        ]
        if eligible_leads:
            lead = eligible_leads[0].model_copy(update={"bucket": "lead"})

    remaining = [
        story
        for story in decorated
        if lead is None or story.story_key != lead.story_key
    ]
    also_pool = [
        story
        for story in remaining
        if desired[story.story_key] in {"lead", "also_matters"}
    ]
    also = [
        story.model_copy(update={"bucket": "also_matters"})
        for story in also_pool[:_MAX_ALSO]
    ]
    overflow = also_pool[_MAX_ALSO:]
    quick_pool = [
        *overflow,
        *[
            story
            for story in remaining
            if desired[story.story_key] == "quick_take"
            and story.story_key not in {item.story_key for item in also_pool}
        ],
    ]
    quick_pool.sort(
        key=lambda item: (
            item.priority_score,
            item.impact_score,
            item.published_at,
            item.primary_source_id,
        ),
        reverse=True,
    )
    quick = [
        story.model_copy(update={"bucket": "quick_take"})
        for story in quick_pool[:_MAX_QUICK]
    ]

    surfaced_source_ids: set[str] = set()
    if lead is not None:
        surfaced_source_ids.update(lead.source_ids)
    for story in [*also, *quick]:
        surfaced_source_ids.update(story.source_ids)

    candidate_ids = set(candidates_by_source)
    published_story_count = (1 if lead is not None else 0) + len(also) + len(quick)
    matched_override_ids = {
        (override.source_id, override.action, override.target_source_id)
        for override in active_overrides
        if override.source_id in candidate_ids
    }
    generated = generated_at or datetime.now(timezone.utc)

    return DailyEditorPage(
        generated_at=generated,
        date=day.isoformat(),
        edition_state=resolved_state,
        cutoff=resolved_cutoff.strftime("%H:%M"),
        quiet_morning=lead is None,
        candidate_count=len(candidate_ids),
        published_story_count=published_story_count,
        other_analysed_count=max(0, len(candidate_ids - surfaced_source_ids)),
        developing_story_count=sum(1 for story in decorated if story.is_developing),
        override_count=len(matched_override_ids),
        lead=lead,
        also_matters=also,
        quick_takes=quick,
    )


def build_daily_editor_timeline(
    *,
    day: date,
    editions: list[DailyEditorPage],
    generated_at: datetime | None = None,
) -> DailyEditorTimeline:
    canonical = [
        page
        for page in editions
        if page.edition_state in {"early_read", "morning_note", "aim_close"}
    ]
    order = {"early_read": 0, "morning_note": 1, "aim_close": 2}
    canonical.sort(key=lambda page: order[str(page.edition_state)])
    transitions: list[DailyEditorTransition] = []
    rank = {"suppressed": 0, "quick_take": 1, "also_matters": 2, "lead": 3}

    for previous, current in zip(canonical, canonical[1:]):
        prev_map = {story.story_key: story for story in _story_list(previous)}
        curr_map = {story.story_key: story for story in _story_list(current)}
        for story_key in sorted(set(prev_map) | set(curr_map)):
            before = prev_map.get(story_key)
            after = curr_map.get(story_key)
            from_bucket: AlgorithmicBucket = before.bucket if before else "suppressed"
            to_bucket: AlgorithmicBucket = after.bucket if after else "suppressed"
            if before is None and after is not None:
                status: TransitionStatus = "new"
                ticker = after.ticker
            elif before is not None and after is None:
                status = "dropped"
                ticker = before.ticker
            elif rank[to_bucket] > rank[from_bucket]:
                status = "promoted"
                ticker = after.ticker if after else before.ticker  # type: ignore[union-attr]
            elif rank[to_bucket] < rank[from_bucket]:
                status = "demoted"
                ticker = after.ticker if after else before.ticker  # type: ignore[union-attr]
            else:
                status = "unchanged"
                ticker = after.ticker if after else before.ticker  # type: ignore[union-attr]
            transitions.append(
                DailyEditorTransition(
                    story_key=story_key,
                    ticker=ticker,
                    from_state=previous.edition_state,  # type: ignore[arg-type]
                    to_state=current.edition_state,  # type: ignore[arg-type]
                    from_bucket=from_bucket,
                    to_bucket=to_bucket,
                    status=status,
                )
            )

    return DailyEditorTimeline(
        generated_at=generated_at or datetime.now(timezone.utc),
        date=day.isoformat(),
        editions=canonical,
        transitions=transitions,
    )
