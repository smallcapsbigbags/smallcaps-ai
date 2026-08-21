from __future__ import annotations

from collections.abc import Mapping, Sequence

from analyst.models import AnnouncementInput

PRIOR_CONTEXT_LIMIT = 8

_TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "results": (
        "result",
        "trading",
        "guidance",
        "profit warning",
        "revenue",
        "ebitda",
        "earnings",
        "margin",
        "outlook",
    ),
    "finance": (
        "cash",
        "debt",
        "facility",
        "funding",
        "fundrais",
        "placing",
        "subscription",
        "liquidity",
        "working capital",
        "covenant",
        "refinanc",
        "going concern",
        "dilution",
        "warrant",
        "convertible",
    ),
    "transaction": (
        "acquisition",
        "disposal",
        "offer",
        "takeover",
        "scheme",
        "merger",
        "strategic review",
        "capital return",
        "buyback",
    ),
    "contract": ("contract", "order", "tender", "customer", "licence", "license"),
    "ownership": (
        "holding",
        "tr-1",
        "director dealing",
        "pdmr",
        "voting rights",
        "concert party",
    ),
    "operations": (
        "production",
        "drilling",
        "resource",
        "reserve",
        "clinical",
        "trial",
        "regulatory approval",
        "fda",
        "project",
        "milestone",
    ),
}


def _normalise(value: object) -> str:
    if isinstance(value, Mapping):
        return " ".join(f"{key} {_normalise(item)}" for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return " ".join(_normalise(item) for item in value)
    return str(value or "")


def _tags(text: str) -> set[str]:
    lowered = text.lower()
    return {
        tag
        for tag, needles in _TAG_PATTERNS.items()
        if any(needle in lowered for needle in needles)
    }


def _query_text(documents: Sequence[AnnouncementInput]) -> str:
    return " ".join(
        f"{document.title} {document.rns_type} {' '.join(document.categories)}"
        for document in documents
    )


def select_prior_context(
    records: Sequence[dict[str, object]],
    documents: Sequence[AnnouncementInput],
    *,
    limit: int = PRIOR_CONTEXT_LIMIT,
) -> list[dict[str, object]]:
    """Select a small, relevant, chronological history without another model call.

    The two most recent records are always retained. Remaining slots favour records
    sharing the current announcement's economic topic. Ties favour recency. The
    returned records preserve chronological order for delta analysis.
    """

    items = list(records)
    if limit <= 0 or not items:
        return []
    if len(items) <= limit:
        return items

    query_tags = _tags(_query_text(documents))
    recent_indices = set(range(max(0, len(items) - min(2, limit)), len(items)))
    slots = max(0, limit - len(recent_indices))

    scored: list[tuple[int, int]] = []
    for index, record in enumerate(items):
        if index in recent_indices:
            continue
        text = _normalise(record)
        record_tags = _tags(text)
        overlap = len(query_tags & record_tags)
        score = overlap * 20 + index

        record_type = str(record.get("rns_type", record.get("type", ""))).lower()
        if "results" in query_tags and "results" in record_type:
            score += 12
        if "ownership" in query_tags and record_type in {
            "holdings",
            "director dealing",
        }:
            score += 12
        if "finance" in query_tags and any(
            marker in text.lower()
            for marker in ("cash", "debt", "facility", "funding", "covenant", "dilution")
        ):
            score += 8
        scored.append((score, index))

    selected_indices = set(recent_indices)
    selected_indices.update(
        index for _score, index in sorted(scored, reverse=True)[:slots]
    )
    return [item for index, item in enumerate(items) if index in selected_indices]
