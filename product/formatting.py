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

_FEED_FACT_LABEL_REWRITES = {
    "notice of intention to appoint administrators": "Administration",
    "going concern funding position": "Funding position",
    "potential shareholder recovery": "Shareholder recovery",
    "possible offer target": "Offer scope",
    "concert party disclosure": "Concert party",
}

_COMPARATOR_NOISE = {
    "not disclosed",
    "not available",
    "n/a",
    "na",
    "none",
    "unknown",
}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalise_impact_colour(colour: object) -> str:
    clean = _clean_text(colour).lower()
    return clean if clean in IMPACT_DIRECTION_LABELS else "grey"


def _normalise_impact_level(level: object) -> str:
    clean = _clean_text(level).lower()
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

    clean = _clean_text(value)
    return "" if clean.lower() in _HIDDEN_PUBLIC_TYPES else clean


def fact_is_numeric(fact: dict[str, Any]) -> bool:
    """Choose numerical typography only when the fact is genuinely compact data."""

    for key in ("value_numeric", "value_low", "value_high"):
        value = fact.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True

    text = _clean_text(fact.get("value"))
    if not text or len(text) > 48 or len(text.split()) > 7:
        return False
    return bool(
        re.search(
            r"(?:[£$€]\s*\d|\b\d[\d,.]*\s*(?:%|pp|x|p|m|bn|shares?)?\b)",
            text,
            flags=re.IGNORECASE,
        )
    )


def compact_feed_fact_label(fact: dict[str, Any]) -> str:
    """Use short noun-phrase evidence labels without changing the stored fact."""

    label = _clean_text(fact.get("label") or fact.get("metric") or "Reported fact")
    replacement = _FEED_FACT_LABEL_REWRITES.get(label.lower())
    return replacement or label


def compact_feed_fact_value(fact: dict[str, Any]) -> str:
    """Expand ambiguous one-word values when the evidence supports a safer phrase."""

    value = _clean_text(fact.get("value"))
    label = _clean_text(fact.get("label") or fact.get("metric")).lower()
    if (
        label == "notice of intention to appoint administrators"
        and value.lower() == "filed"
    ):
        return "Notice of intention filed"
    return value


def feed_comparator_text(fact: dict[str, Any]) -> str:
    """Return a comparator only when it adds useful prior-state information."""

    current = _clean_text(fact.get("value"))
    candidates = (fact.get("previous_value"), fact.get("comparator"))
    for candidate in candidates:
        clean = _clean_text(candidate)
        if not clean or clean == current:
            continue
        lower = clean.lower()
        if lower in _COMPARATOR_NOISE:
            continue
        if "not disclosed" in lower or "not available" in lower:
            continue
        if "supplied prior context" in lower or "coverage is building" in lower:
            continue
        if re.fullmatch(r"no .+ disclosed", lower):
            continue
        return clean
    return ""


def _feed_context(item: dict[str, Any]) -> str:
    fact_text = " ".join(
        f"{_clean_text(fact.get('label'))} {_clean_text(fact.get('value'))}"
        for fact in list(item.get("key_facts") or [])
    )
    return " ".join(
        part
        for part in (
            _clean_text(item.get("headline")),
            _clean_text(item.get("takeaway")),
            _clean_text(item.get("impact_rationale")),
            _clean_text(item.get("analyst_view")),
            fact_text,
        )
        if part
    ).lower()


def _has_offer_terms(context: str) -> bool:
    if any(
        phrase in context
        for phrase in (
            "offer price",
            "price per share",
            "pence per share",
            "cash per share",
        )
    ):
        return True
    return bool(
        re.search(
            r"(?:£\s*\d[\d,.]*|\b\d+(?:\.\d+)?p)\s+(?:per share|a share)\b",
            context,
        )
    )


def feed_verdict(item: dict[str, Any]) -> str:
    """Return a concise display verdict for high-confidence event patterns.

    This is a presentation adapter, not a new analytical model. It only replaces
    the stored headline when the existing fields jointly support a narrower,
    simpler investor outcome; otherwise the stored analyst headline is preserved.
    """

    headline = _clean_text(item.get("headline"))
    context = _feed_context(item)

    has_administration = bool(re.search(r"\badministrat(?:ion|or|ors|ing)\b", context))
    has_no_shareholder_return = bool(
        re.search(r"\bno (?:return|returns)\b", context) and "shareholder" in context
    )
    has_funding_shortfall = (
        "insufficient funds" in context
        or "going concern" in context
        or "funding shortfall" in context
    )
    if has_administration and has_no_shareholder_return:
        return "Administration imminent; no shareholder return expected"
    if has_administration and has_funding_shortfall:
        return "Administration imminent after funding shortfall"

    possible_offer = (
        "possible offer" in context
        or "takeover talks" in context
        or "rule 2.4" in context
    )
    if possible_offer and not _has_offer_terms(context):
        return "Formal takeover interest emerges; terms remain unknown"

    return headline


def _truncate_words(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars + 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return clipped + "…"


def concise_feed_view(text: object, *, max_sentences: int = 2, max_chars: int = 280) -> str:
    """Compress an analyst sentence block for the feed without inventing content."""

    clean = _clean_text(text)
    if not clean:
        return ""
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(clean) if part.strip()]
    chosen = " ".join(sentences[:max_sentences]) if sentences else clean
    return _truncate_words(chosen, max_chars)


def feed_view(item: dict[str, Any]) -> str:
    """Return the shortest useful interpretation for the scan-first Feed."""

    context = _feed_context(item)
    if (
        re.search(r"\badministrat(?:ion|or|ors|ing)\b", context)
        and re.search(r"\bno (?:return|returns)\b", context)
        and "shareholder" in context
    ):
        return (
            "Thesis broken. This is now an insolvency and asset-recovery situation, "
            "not an operating investment case."
        )

    if (
        ("possible offer" in context or "takeover talks" in context or "rule 2.4" in context)
        and not _has_offer_terms(context)
    ):
        return (
            "A formal takeover process can reset valuation expectations, but no offer "
            "terms are disclosed yet."
        )

    source = item.get("impact_rationale") or item.get("analyst_view") or ""
    return concise_feed_view(source)


def attention_summary_label(count: int) -> str:
    if count == 1:
        return "1 announcement needs attention"
    return f"{count} announcements need attention"


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
        if fact.get("basis") in {"not-disclosed", "source-warning"} or not _clean_text(
            fact.get("value")
        ):
            continue
        output.append(fact)
        if len(output) >= limit:
            break
    return output


def attention_count(items: list[dict[str, Any]]) -> int:
    return sum(1 for item in items if int(item.get("impact_score") or 0) >= 3)
