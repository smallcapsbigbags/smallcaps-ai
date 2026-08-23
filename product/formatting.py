from __future__ import annotations

import re
from datetime import datetime
from typing import Any

IMPACT_HEX = {
    "green": "#2E8B57",
    "red": "#C44D56",
    "amber": "#B98224",
    "grey": "#7A838B",
}

IMPACT_DIRECTION_LABELS = {
    "green": "FAVOURABLE",
    "red": "ADVERSE",
    "amber": "MIXED",
    "grey": "NEUTRAL",
}

IMPACT_LEVELS = {"low", "medium", "high", "critical"}
_HIDDEN_PUBLIC_TYPES = {"other", "unknown", "uncategorised", "unclassified"}


def _normalise_impact_colour(colour: object) -> str:
    clean = str(colour or "").strip().lower()
    return clean if clean in IMPACT_DIRECTION_LABELS else "grey"


def _normalise_impact_level(level: object) -> str:
    clean = str(level or "").strip().lower()
    return clean if clean in IMPACT_LEVELS else "low"


def impact_hex(colour: str) -> str:
    return IMPACT_HEX[_normalise_impact_colour(colour)]


def impact_direction_label(colour: str, *, level: str = "") -> str:
    """Translate an internal colour token into investor-facing language.

    The public interface describes investment meaning rather than exposing
    implementation labels such as RED or GREEN. Low-impact grey records are
    routine; higher-impact grey records are directionally neutral.
    """

    clean_colour = _normalise_impact_colour(colour)
    clean_level = _normalise_impact_level(level)
    if clean_colour == "grey" and clean_level == "low":
        return "ROUTINE"
    return IMPACT_DIRECTION_LABELS[clean_colour]


def impact_signal_label(colour: str, level: str) -> str:
    """Return the accessible public impact signal used across the product."""

    clean_level = _normalise_impact_level(level)
    return f"{clean_level.upper()} · {impact_direction_label(colour, level=clean_level)}"


def public_rns_type(value: object) -> str:
    """Hide fallback taxonomy labels that add no investor information."""

    clean = " ".join(str(value or "").strip().split())
    return "" if clean.lower() in _HIDDEN_PUBLIC_TYPES else clean


def fact_is_numeric(fact: dict[str, Any]) -> bool:
    """Choose numerical typography only when the fact is genuinely compact data."""

    for key in ("value_numeric", "value_low", "value_high"):
        value = fact.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True

    text = " ".join(str(fact.get("value") or "").strip().split())
    if not text or len(text) > 48 or len(text.split()) > 7:
        return False
    return bool(
        re.search(
            r"(?:[£$€]\s*\d|\b\d[\d,.]*\s*(?:%|pp|x|p|m|bn|shares?)?\b)",
            text,
            flags=re.IGNORECASE,
        )
    )


def format_price_change(price: dict[str, Any] | None) -> str:
    if not price or price.get("daily_change_pct") is None:
        return "—"
    return f"{float(price['daily_change_pct']):+.1f}%"


def format_price_context(price: dict[str, Any] | None) -> str:
    if not price or price.get("daily_change_pct") is None:
        return "Market reaction pending"
    move = format_price_change(price)
    return (
        f"{move} at close"
        if str(price.get("phase") or "intraday") == "close"
        else f"{move} today"
    )


def format_market_price(value: object, *, currency: str = "GBp") -> str:
    if value is None:
        return "—"
    number = float(value)
    if currency == "GBp":
        return f"{number:.2f}p"
    return f"{currency} {number:,.2f}" if currency else f"{number:,.2f}"


def format_time(value: str | datetime) -> str:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed.strftime("%H:%M")


def format_day(value: str | datetime) -> str:
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    return parsed.strftime("%-d %b %Y")


def select_feed_facts(
    facts: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    output = []
    for fact in facts:
        if fact.get("basis") in {"not-disclosed", "source-warning"} or not str(
            fact.get("value") or ""
        ).strip():
            continue
        output.append(fact)
        if len(output) >= limit:
            break
    return output


def attention_count(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if int(item.get("impact_score") or 0) >= 3)
