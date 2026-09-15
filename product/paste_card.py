"""Deterministic display selection. Never rewrite facts or calculate from strings."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

CARD_LAYOUT_VERSION = "paste-card-2"


def _text(fact: Mapping[str, object]) -> str:
    return " ".join(f"{fact.get('metric') or ''} {fact.get('label') or ''}".lower().split())


def _family(fact: Mapping[str, object]) -> str:
    text = _text(fact)
    rules = (
        ("runway", r"\brunway\b|cash burn|burn rate"),
        ("balance", r"\bcash\b|\bdebt\b|liquidity|covenant"),
        ("dividend", r"dividend|distribution per share"),
        ("dilution", r"dilution|new shares|enlarged share|placing discount"),
        ("funding", r"placing proceeds|fundrais|funding amount|facility size"),
        ("margin", r"margin|cash conversion"),
        ("earnings-per-share", r"\beps\b|earnings per share"),
        ("profit", r"profit|\bpbt\b|\bebitda?\b|operating loss"),
        ("revenue", r"revenue|\bsales\b|\barr\b|net fee income"),
        ("value", r"contract value|consideration|offer price|purchase price|order value"),
        ("duration", r"duration|development|programme length|contract term|lease term"),
        ("start", r"production|launch|start date|completion date|deadline"),
    )
    for family, pattern in rules:
        if re.search(pattern, text):
            return family
    # Unrelated sector KPIs must not all collapse into a generic "other" bucket.
    return "other:" + str(fact.get("metric") or fact.get("label") or "").strip().lower()


def _preference(fact: Mapping[str, object]) -> int:
    """Prefer an explicitly group-level KPI and net balance, not an arbitrary segment."""
    text = _text(fact)
    if _family(fact) == "balance":
        return 0 if re.search(r"net (?:bank )?(?:cash|debt)", text) else 1
    return 1 if re.search(r"private housing|affordable housing|land sales|\bsegment\b|\bdivision\b", text) else 0


def select_metric_indexes(
    facts: Sequence[Mapping[str, object]], rns_type: str, *, limit: int = 4,
) -> list[int]:
    """Choose up to four *existing* numbers, retaining all other facts in the record.

    Results favour revenue/profit/net balance/dividend; contracts favour value,
    duration, timing and revenue. Within a family keep the analyst's order, except
    for explicit group/segment and net/gross distinctions. This is a display policy,
    not a materiality score, financial normalisation or semantic fact-check.
    """
    limit = max(0, min(limit, 4))
    candidates = [i for i, fact in enumerate(facts)
        if fact.get("basis") in {"reported", "calculated"}
        and fact.get("information_status") != "not-disclosed"
        and re.search(r"\d", str(fact.get("value") or ""))]
    groups: dict[str, list[int]] = {}
    for index in candidates:
        groups.setdefault(_family(facts[index]), []).append(index)
    for indexes in groups.values():
        indexes.sort(key=lambda i: (_preference(facts[i]), i))
    priorities = {
        "Results & trading": ("revenue", "profit", "balance", "dividend"),
        "Contracts": ("value", "duration", "start", "revenue"),
        "Funding & solvency": ("balance", "runway", "funding", "start"),
        "Fundraising": ("funding", "dilution", "balance", "runway"),
        "Takeover": ("value", "start"),
        "Acquisition": ("value", "profit", "funding", "balance"),
    }.get(rns_type, ())
    selected: list[int] = []
    used: set[str] = set()
    for family in (*priorities, *groups):
        if family in used or family not in groups:
            continue
        if len(selected) >= limit:
            break
        selected.append(groups[family][0])
        used.add(family)
    return selected
