from __future__ import annotations

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


def impact_hex(colour: str) -> str:
    return IMPACT_HEX.get(colour, IMPACT_HEX["grey"])


def impact_direction_label(colour: str, *, level: str = "") -> str:
    """Translate an internal colour token into investor-facing language.

    The public interface should describe investment meaning rather than expose
    implementation labels such as RED or GREEN. Low-impact grey records are
    routine; higher-impact grey records are directionally neutral.
    """

    clean_colour = str(colour or "").strip().lower()
    if clean_colour not in IMPACT_DIRECTION_LABELS:
        clean_colour = "grey"
    if clean_colour == "grey" and str(level or "").strip().lower() == "low":
        return "ROUTINE"
    return IMPACT_DIRECTION_LABELS[clean_colour]


def impact_signal_label(colour: str, level: str) -> str:
    """Return the semantic public signal reserved for the Jobs UX pass."""

    clean_level = str(level or "low").strip().upper() or "LOW"
    return f"{clean_level} · {impact_direction_label(colour, level=level)}"


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
