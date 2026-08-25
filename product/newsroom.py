from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from product.daily_editor import DailyEditorBucket, DailyEditorPage, DailyEditorStory

NEWSROOM_SCHEMA_VERSION = "aim-daily-newsroom-v1"
NEWSROOM_VERSION = "aim-daily-newsroom-1.0"

ClaimKind = Literal["news", "context", "view", "catch", "missing", "next_test"]
CopyDeskStatus = Literal["pass", "fail"]

BANNED_AI_PHRASES: tuple[str, ...] = (
    "underscores",
    "showcases",
    "highlights the company's commitment",
    "represents a significant",
    "notably",
    "importantly",
    "demonstrates",
)

_METRIC_PRIORITY: tuple[tuple[str, int], ...] = (
    ("net debt", 40),
    ("net cash", 40),
    ("liquidity", 38),
    ("covenant", 38),
    ("cash conversion", 36),
    ("free cash flow", 36),
    ("profit guidance", 35),
    ("ebitda guidance", 35),
    ("revenue guidance", 34),
    ("ebitda", 30),
    ("profit", 29),
    ("margin", 28),
    ("revenue", 24),
    ("order book", 23),
    ("arr", 23),
    ("production", 22),
    ("completions", 22),
)

_GUIDANCE_STATUS_PRIORITY = {
    "downgraded": 60,
    "withdrawn": 58,
    "upgraded": 55,
    "missed": 50,
    "issued": 42,
    "maintained": 30,
    "reiterated": 28,
    "delivered": 25,
}

_NUMBER_RE = re.compile(r"(?<![A-Za-z])(?:£|\$|€)?-?\d[\d,]*(?:\.\d+)?%?(?:m|bn|k)?", re.I)


class NewsroomModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewsroomEvidenceRef(NewsroomModel):
    source_id: str
    source_url: str = ""
    published_at: str = ""
    field_path: str
    label: str = ""


class NewsroomClaim(NewsroomModel):
    kind: ClaimKind
    text: str
    provenance: list[NewsroomEvidenceRef] = Field(default_factory=list)


class NewsroomNumberPoint(NewsroomModel):
    value: str
    published_at: str
    source_id: str
    source_url: str = ""


class NewsroomNumber(NewsroomModel):
    label: str
    metric: str
    points: list[NewsroomNumberPoint] = Field(default_factory=list)
    direction: Literal["up", "down", "flat", "unclear"] = "unclear"


class NewsroomArticle(NewsroomModel):
    story_key: str
    story_family: str
    ticker: str
    company: str
    bucket: DailyEditorBucket
    impact_score: int = Field(ge=1, le=5)
    signal: str
    outlook: str
    headline: str
    news: NewsroomClaim
    context: list[NewsroomClaim] = Field(default_factory=list)
    view: NewsroomClaim
    the_number: NewsroomNumber | None = None
    the_catch: NewsroomClaim | None = None
    whats_missing: list[NewsroomClaim] = Field(default_factory=list)
    next_test: NewsroomClaim | None = None
    source_ids: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    copydesk_status: CopyDeskStatus
    copydesk_flags: list[str] = Field(default_factory=list)


class NewsroomEdition(NewsroomModel):
    schema_version: Literal["aim-daily-newsroom-v1"] = NEWSROOM_SCHEMA_VERSION
    newsroom_version: Literal["aim-daily-newsroom-1.0"] = NEWSROOM_VERSION
    generated_at: datetime
    date: str
    edition_state: str
    cutoff: str
    source_editor_schema: str
    source_editor_version: str
    screened_candidate_count: int = Field(ge=0)
    selected_story_count: int = Field(ge=0)
    published_article_count: int = Field(ge=0)
    withheld_story_count: int = Field(ge=0)
    other_analysed_count: int = Field(ge=0)
    lead: NewsroomArticle | None = None
    also_matters: list[NewsroomArticle] = Field(default_factory=list)
    quick_takes: list[NewsroomArticle] = Field(default_factory=list)


class NewsroomFact(NewsroomModel):
    source_id: str
    source_url: str = ""
    published_at: str = ""
    label: str
    metric: str = ""
    period: str = ""
    value: str
    previous_value: str = ""
    comparator: str = ""
    comparator_source_id: str = ""
    basis: str = "reported"
    unit: str = ""
    currency: str = ""
    information_status: str = "new"


class NewsroomGuidance(NewsroomModel):
    source_id: str
    source_url: str = ""
    published_at: str = ""
    metric: str
    period: str = ""
    value: str = ""
    status: str
    comparator: str = ""
    previous_value: str = ""
    previous_source_id: str = ""
    note: str = ""


class NewsroomMetricHistory(NewsroomModel):
    metric: str
    label: str
    points: list[NewsroomNumberPoint] = Field(default_factory=list)
    direction: Literal["up", "down", "flat", "unclear"] = "unclear"


@dataclass(slots=True)
class NewsroomStoryPacket:
    story: DailyEditorStory
    facts: list[NewsroomFact] = field(default_factory=list)
    guidance: list[NewsroomGuidance] = field(default_factory=list)
    metric_history: list[NewsroomMetricHistory] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)
    watch_items: list[str] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    management_language_mismatch: str = ""
    open_claims: list[tuple[str, str, str, str]] = field(default_factory=list)
    evidence_texts: list[str] = field(default_factory=list)
    source_published_at: dict[str, str] = field(default_factory=dict)
    source_urls: dict[str, str] = field(default_factory=dict)


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _sentence(value: object) -> str:
    text = _clean(value)
    replacements = (
        ("Importantly, ", ""),
        ("Notably, ", ""),
        ("importantly, ", ""),
        ("notably, ", ""),
        ("underscores", "shows"),
        ("demonstrates", "shows"),
        ("showcases", "shows"),
        ("highlights the company's commitment to", "shows"),
        ("represents a significant", "is a"),
    )
    for before, after in replacements:
        text = text.replace(before, after)
    if text and text[-1] not in ".?!":
        text += "."
    return text


def _headline(value: object) -> str:
    text = _clean(value).rstrip(". ")
    for prefix in ("The company announces ", "Company announces ", "Announcement of "):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix) :]
            break
    return text[:180].strip()


def _metric_score(value: object) -> int:
    metric = _clean(value).lower()
    return max((score for marker, score in _METRIC_PRIORITY if marker in metric), default=0)


def _guidance_score(item: NewsroomGuidance) -> int:
    return _GUIDANCE_STATUS_PRIORITY.get(item.status.lower(), 0) + _metric_score(item.metric)


def _fact_score(item: NewsroomFact) -> int:
    score = _metric_score(item.metric or item.label)
    if item.previous_value:
        score += 20
    if item.information_status == "new":
        score += 5
    if item.basis == "reported":
        score += 3
    return score


def _ref(
    packet: NewsroomStoryPacket,
    source_id: str,
    *,
    field_path: str,
    label: str = "",
) -> NewsroomEvidenceRef:
    return NewsroomEvidenceRef(
        source_id=source_id,
        source_url=packet.source_urls.get(source_id, ""),
        published_at=packet.source_published_at.get(source_id, ""),
        field_path=field_path,
        label=label,
    )


def _guidance_news(packet: NewsroomStoryPacket) -> NewsroomClaim | None:
    candidates = [item for item in packet.guidance if item.status.lower() in _GUIDANCE_STATUS_PRIORITY]
    if not candidates:
        return None
    item = max(candidates, key=lambda value: (_guidance_score(value), value.metric, value.period))
    status = item.status.lower()
    verb = {
        "downgraded": "cut",
        "withdrawn": "withdrew",
        "upgraded": "raised",
        "missed": "missed",
        "issued": "set",
        "maintained": "maintained",
        "reiterated": "reiterated",
        "delivered": "delivered",
    }.get(status, "updated")
    subject = packet.story.company or packet.story.ticker
    period = f" for {item.period}" if item.period else ""
    if status == "withdrawn":
        text = f"{subject} withdrew {item.metric} guidance{period}"
    elif item.value and item.previous_value and status in {"downgraded", "upgraded"}:
        text = f"{subject} {verb} {item.metric} guidance{period} to {item.value} from {item.previous_value}"
    elif item.value:
        text = f"{subject} {verb} {item.metric} guidance{period} at {item.value}"
    else:
        text = f"{subject} {verb} {item.metric} guidance{period}"
    refs = [_ref(packet, item.source_id, field_path="guidance_events", label=item.metric)]
    if item.previous_source_id:
        refs.append(_ref(packet, item.previous_source_id, field_path="guidance_events.previous_value", label=item.metric))
    return NewsroomClaim(kind="news", text=_sentence(text), provenance=refs)


def _fact_news(packet: NewsroomStoryPacket) -> NewsroomClaim | None:
    candidates = [item for item in packet.facts if item.value and item.basis != "not-disclosed"]
    if not candidates:
        return None
    item = max(candidates, key=lambda value: (_fact_score(value), value.metric, value.label))
    subject = packet.story.company or packet.story.ticker
    label = item.label or item.metric
    if item.previous_value:
        text = f"{subject} reported {label} of {item.value}, versus {item.previous_value} at the prior comparable disclosure"
    else:
        text = f"{subject} reported {label} of {item.value}"
    refs = [_ref(packet, item.source_id, field_path="facts", label=label)]
    if item.comparator_source_id:
        refs.append(_ref(packet, item.comparator_source_id, field_path="facts.previous_value", label=label))
    return NewsroomClaim(kind="news", text=_sentence(text), provenance=refs)


def _fallback_news(packet: NewsroomStoryPacket) -> NewsroomClaim:
    source_ids = packet.story.source_ids or [packet.story.primary_source_id]
    return NewsroomClaim(
        kind="news",
        text=_sentence(packet.story.what_changed),
        provenance=[_ref(packet, source_id, field_path="analyst_run.what_changed.today") for source_id in source_ids],
    )


def _context_claims(packet: NewsroomStoryPacket) -> list[NewsroomClaim]:
    histories = [item for item in packet.metric_history if len(item.points) >= 2]
    histories.sort(key=lambda item: (_metric_score(item.metric), len(item.points)), reverse=True)
    output: list[NewsroomClaim] = []
    for history in histories[:2]:
        points = history.points[-3:]
        latest = points[-1]
        previous = points[-2]
        if len(points) >= 3:
            oldest = points[0]
            text = f"{history.label} has moved from {oldest.value} to {previous.value} and now {latest.value} across the last three comparable disclosures"
        else:
            text = f"{history.label} is now {latest.value}, from {previous.value} at the prior comparable disclosure"
        refs = [
            NewsroomEvidenceRef(
                source_id=point.source_id,
                source_url=point.source_url,
                published_at=point.published_at,
                field_path="facts.metric_history",
                label=history.label,
            )
            for point in points
        ]
        output.append(NewsroomClaim(kind="context", text=_sentence(text), provenance=refs))
    return output


def _number(packet: NewsroomStoryPacket) -> NewsroomNumber | None:
    histories = [item for item in packet.metric_history if len(item.points) >= 2]
    if not histories:
        return None
    history = max(histories, key=lambda item: (_metric_score(item.metric), len(item.points)))
    return NewsroomNumber(
        label=history.label,
        metric=history.metric,
        points=history.points[-3:],
        direction=history.direction,
    )


def _view(packet: NewsroomStoryPacket) -> NewsroomClaim:
    source_ids = packet.story.source_ids or [packet.story.primary_source_id]
    return NewsroomClaim(
        kind="view",
        text=_sentence(packet.story.why_it_matters),
        provenance=[_ref(packet, source_id, field_path="analyst_run.analyst_view") for source_id in source_ids],
    )


def _catch(packet: NewsroomStoryPacket) -> NewsroomClaim | None:
    text = _clean(packet.challenges[0]) if packet.challenges else _clean(packet.management_language_mismatch)
    if not text:
        return None
    source_id = packet.story.primary_source_id
    field_path = "analyst_run.challenges_case" if packet.challenges else "analyst_run.disclosure_assessment.management_language_mismatch"
    return NewsroomClaim(kind="catch", text=_sentence(text), provenance=[_ref(packet, source_id, field_path=field_path)])


def _missing(packet: NewsroomStoryPacket) -> list[NewsroomClaim]:
    source_id = packet.story.primary_source_id
    return [
        NewsroomClaim(
            kind="missing",
            text=_sentence(item),
            provenance=[_ref(packet, source_id, field_path="analyst_run.disclosure_assessment.missing_items")],
        )
        for item in packet.missing_items[:3]
        if _clean(item)
    ]


def _next_test(packet: NewsroomStoryPacket) -> NewsroomClaim | None:
    source_id = packet.story.primary_source_id
    if packet.watch_items:
        return NewsroomClaim(
            kind="next_test",
            text=_sentence(packet.watch_items[0]),
            provenance=[_ref(packet, source_id, field_path="analyst_run.watch_items")],
        )
    if packet.open_claims:
        claim, target_date, claim_source_id, claim_source_url = packet.open_claims[0]
        text = claim if not target_date else f"{claim} Target date: {target_date}"
        return NewsroomClaim(
            kind="next_test",
            text=_sentence(text),
            provenance=[
                NewsroomEvidenceRef(
                    source_id=claim_source_id,
                    source_url=claim_source_url,
                    field_path="management_claims",
                    label="open management commitment",
                )
            ],
        )
    return None


def _numeric_tokens(value: str) -> set[str]:
    return {match.group(0).lower().replace(",", "") for match in _NUMBER_RE.finditer(value)}


def _evidence_tokens(packet: NewsroomStoryPacket) -> set[str]:
    joined = " ".join(packet.evidence_texts)
    return _numeric_tokens(joined)


def _valid_url(value: str) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _copydesk(packet: NewsroomStoryPacket, article: NewsroomArticle) -> list[str]:
    flags: list[str] = []
    claims = [article.news, *article.context, article.view]
    if article.the_catch is not None:
        claims.append(article.the_catch)
    claims.extend(article.whats_missing)
    if article.next_test is not None:
        claims.append(article.next_test)

    if not article.headline.strip():
        flags.append("HEADLINE_BLANK")
    if not article.news.text.strip():
        flags.append("NEWS_BLANK")
    if not article.view.text.strip():
        flags.append("VIEW_BLANK")

    all_copy = " ".join([article.headline, *(claim.text for claim in claims)]).lower()
    for phrase in BANNED_AI_PHRASES:
        if phrase in all_copy:
            flags.append(f"HOUSE_STYLE:{phrase}")

    for claim in claims:
        if claim.kind != "view" and not claim.provenance:
            flags.append(f"MISSING_PROVENANCE:{claim.kind}")
        for ref in claim.provenance:
            if not ref.source_id.strip():
                flags.append(f"EMPTY_SOURCE_ID:{claim.kind}")
            if not _valid_url(ref.source_url):
                flags.append(f"INVALID_SOURCE_URL:{ref.source_id}")

    supported_numbers = _evidence_tokens(packet)
    for claim in [article.news, *article.context]:
        unsupported = sorted(_numeric_tokens(claim.text) - supported_numbers)
        for token in unsupported:
            flags.append(f"UNSUPPORTED_NUMBER:{token}")

    word_limits = {
        "headline": (article.headline, 18),
        "news": (article.news.text, 70),
        "view": (article.view.text, 65),
    }
    for name, (value, limit) in word_limits.items():
        if len(value.split()) > limit:
            flags.append(f"WORD_LIMIT:{name}:{len(value.split())}>{limit}")
    for index, claim in enumerate(article.context):
        if len(claim.text.split()) > 55:
            flags.append(f"WORD_LIMIT:context[{index}]")

    return list(dict.fromkeys(flags))


def build_newsroom_article(packet: NewsroomStoryPacket) -> NewsroomArticle:
    news = _guidance_news(packet) or _fact_news(packet) or _fallback_news(packet)
    article = NewsroomArticle(
        story_key=packet.story.story_key,
        story_family=packet.story.story_family,
        ticker=packet.story.ticker,
        company=packet.story.company,
        bucket=packet.story.bucket,
        impact_score=packet.story.impact_score,
        signal=str(packet.story.signal),
        outlook=str(packet.story.outlook),
        headline=_headline(packet.story.editorial_headline),
        news=news,
        context=_context_claims(packet),
        view=_view(packet),
        the_number=_number(packet),
        the_catch=_catch(packet),
        whats_missing=_missing(packet),
        next_test=_next_test(packet),
        source_ids=list(packet.story.source_ids),
        source_urls=list(packet.story.source_urls),
        copydesk_status="pass",
    )
    flags = _copydesk(packet, article)
    return article.model_copy(
        update={
            "copydesk_status": "fail" if flags else "pass",
            "copydesk_flags": flags,
        }
    )


def build_newsroom_edition(
    *,
    editor_page: DailyEditorPage,
    packets: list[NewsroomStoryPacket],
    generated_at: datetime | None = None,
) -> NewsroomEdition:
    by_key = {packet.story.story_key: build_newsroom_article(packet) for packet in packets}

    def article_for(story: DailyEditorStory | None) -> NewsroomArticle | None:
        if story is None:
            return None
        article = by_key.get(story.story_key)
        if article is None or article.copydesk_status != "pass":
            return None
        return article

    lead = article_for(editor_page.lead)
    also = [article for story in editor_page.also_matters if (article := article_for(story)) is not None]
    quick = [article for story in editor_page.quick_takes if (article := article_for(story)) is not None]
    selected = editor_page.published_story_count
    published = (1 if lead is not None else 0) + len(also) + len(quick)
    return NewsroomEdition(
        generated_at=generated_at or datetime.now(timezone.utc),
        date=editor_page.date,
        edition_state=editor_page.edition_state,
        cutoff=editor_page.cutoff,
        source_editor_schema=editor_page.schema_version,
        source_editor_version=editor_page.editor_version,
        screened_candidate_count=editor_page.candidate_count,
        selected_story_count=selected,
        published_article_count=published,
        withheld_story_count=max(0, selected - published),
        other_analysed_count=editor_page.other_analysed_count,
        lead=lead,
        also_matters=also,
        quick_takes=quick,
    )
