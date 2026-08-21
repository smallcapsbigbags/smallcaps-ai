from __future__ import annotations

from datetime import datetime
from typing import Any

IMPACT_HEX = {
    "green": "#2E8B57",
    "red": "#C44D56",
    "amber": "#B98224",
    "grey": "#7A838B",
}


def impact_hex(colour: str) -> str:
    return IMPACT_HEX.get(colour, IMPACT_HEX["grey"])


def format_price_change(price: dict[str, Any] | None) -> str:
    if not price:
        return "—"
    value = price.get("daily_change_pct")
    if value is None:
        return "—"
    number = float(value)
    return f"{number:+.1f}%"


def format_price_context(price: dict[str, Any] | None) -> str:
    if not price:
        return "Market reaction pending"
    phase = str(price.get("phase") or "intraday")
    move = format_price_change(price)
    if phase == "close":
        return f"{move} at close"
    return f"{move} today"


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
        if fact.get("basis") in {"not-disclosed", "source-warning"}:
            continue
        if not str(fact.get("value") or "").strip():
            continue
        output.append(fact)
        if len(output) >= limit:
            break
    return output


def attention_count(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if int(item.get("impact_score") or 0) >= 3)
