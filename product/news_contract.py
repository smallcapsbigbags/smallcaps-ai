from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PRODUCT_NAME = "smallcaps.ai"
PRODUCT_TAGLINE = "AIM company news. Facts. No fluff."
KEY_NEWS_MIN_MATERIALITY = 3

Direction = Literal["positive", "mixed", "negative", "neutral"]
DirectionColour = Literal["green", "amber", "red", "grey"]
BaselineStatus = Literal["building", "established"]
ChangeDirection = Literal["up", "down", "flat", "new", "unclear"]
ChangeBasis = Literal["compared", "explicit-transition"]
FactBasis = Literal[
    "reported",
    "calculated",
    "compared",
    "not-disclosed",
    "source-warning",
]

DIRECTION_BY_COLOUR: dict[DirectionColour, Direction] = {
    "green": "positive",
    "amber": "mixed",
    "red": "negative",
    "grey": "neutral",
}

DIRECTION_LABELS: dict[Direction, str] = {
    "positive": "Positive",
    "mixed": "Mixed",
    "negative": "Negative",
    "neutral": "Neutral",
}

MATERIALITY_LABELS: dict[int, str] = {
    1: "Routine",
    2: "Minor",
    3: "Material",
    4: "High",
    5: "Critical",
}


class ProductContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def direction_from_colour(colour: DirectionColour) -> Direction:
    """Map the analyst engine's existing colour field to public direction language."""

    return DIRECTION_BY_COLOUR[colour]


def materiality_circles(score: int) -> str:
    """Render materiality independently of direction using five neutral circles."""

    if score not in MATERIALITY_LABELS:
        raise ValueError("materiality score must be between 1 and 5")
    return "●" * score + "○" * (5 - score)


def is_key_news(score: int) -> bool:
    """Default Key News policy: surface materiality 3–5 and hide 1–2."""

    if score not in MATERIALITY_LABELS:
        raise ValueError("materiality score must be between 1 and 5")
    return score >= KEY_NEWS_MIN_MATERIALITY


class MaterialFact(ProductContractModel):
    """One decision-useful factual item retained in the expanded news record."""

    label: str
    value: str
    basis: FactBasis = "reported"
    source_id: str
    source_url: str = ""
    note: str = ""

    @field_validator("label", "value", "source_id")
    @classmethod
    def required_text(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned


class SupportedChange(ProductContractModel):
    """A delta backed by a valid comparator or explicit current-state transition."""

    label: str
    direction: ChangeDirection
    today: str
    before: str = ""
    basis: ChangeBasis = "compared"
    source_id: str
    comparator_source_id: str = ""
    note: str = ""

    @field_validator("label", "today", "source_id")
    @classmethod
    def required_text(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @model_validator(mode="after")
    def require_supported_change(self) -> "SupportedChange":
        if self.basis == "compared" and not self.before.strip():
            raise ValueError("compared changes require a supported before value")
        return self


class MarketReaction(ProductContractModel):
    """MVP price context. Longer event-study windows are deliberately deferred."""

    currency: str = "GBp"
    pre_announcement_price: float | None = None
    day_reaction_pct: float | None = None
    reaction_session: str = ""
    phase: Literal["pending", "pre-open", "intraday", "close"] = "pending"


class CompanyNewsItem(ProductContractModel):
    """Locked public contract for the compact Facts. No fluff. news experience."""

    source_id: str
    ticker: str
    company: str
    published_at: datetime
    news_type: str
    direction: Direction
    materiality: int = Field(ge=1, le=5)
    headline: str = Field(min_length=4, max_length=140)
    take: str
    material_facts: list[MaterialFact] = Field(default_factory=list)
    changes: list[SupportedChange] = Field(default_factory=list)
    baseline_status: BaselineStatus = "building"
    watch_next: list[str] = Field(default_factory=list)
    source_url: str = ""
    market: MarketReaction | None = None

    @field_validator("source_id", "ticker", "company", "news_type", "headline", "take")
    @classmethod
    def compact_required_text(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, value: str) -> str:
        return value.upper().replace(".L", "").rstrip(".-")

    @field_validator("take")
    @classmethod
    def enforce_compact_take(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned.split()) > 45:
            raise ValueError("take must be 45 words or fewer")
        return cleaned

    @property
    def key_news(self) -> bool:
        return is_key_news(self.materiality)

    @property
    def materiality_display(self) -> str:
        return materiality_circles(self.materiality)

    @property
    def direction_label(self) -> str:
        return DIRECTION_LABELS[self.direction]
