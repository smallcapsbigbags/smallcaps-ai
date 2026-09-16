"""Scan all pasted text locally; select bounded, verbatim passages for one card.

Offsets refer to the validated paste, never an AI rewrite. Selection is a heuristic,
not a claim to detect every material disclosure. No first-N-characters truncation.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from .schema import CardError

MAX_EXCERPT_BYTES = 18_000
MAX_PASSAGES = 24
BLOCK_CHARS = 1_500

TOPICS = {
    "highlights": r"financial highlights|operational highlights|key highlights",
    "financial": r"financial review|financial performance|profit and loss|income statement|cash flow|balance sheet",
    "outlook": r"outlook|current trading|trading outlook|guidance",
    "capital": r"dividend|capital returns|returning capital|share buyback|placing|fundrais|subscription",
    "subsequent": r"subsequent events|events after|post[- ](?:year|period)|since (?:year|period)[- ]end|after (?:the )?(?:year|period)[- ]end",
    "risk": r"going concern|material uncertainty|liquidity|covenant|profit warning|administration|suspension",
    "commercial": r"contract|agreement|acquisition|development|production|deployment",
}
PATTERNS = {k: re.compile(v, re.I) for k, v in TOPICS.items()}
HEADING = re.compile(r"^(?:\d+(?:\.\d+)*[.\s]+)?(?:" + "|".join(TOPICS.values()) + r")", re.I)
# All matching blocks are mandatory. If too many fit poorly, fail before spending,
# rather than send an apparently comprehensive but cherry-picked source packet.
CRITICAL = re.compile(
    r"material uncertainty|(?:breach|breached|breaching).{0,60}covenant|"
    r"(?:administration|liquidation|insolven\w*)|"
    r"(?:post[- ]year[- ]end|subsequent|since year[- ]end|after (?:the )?year[- ]end)"
    r"[\s\S]{0,400}?(?:paid|payment|consideration)|"
    r"(?:paid|payment|consideration)[\s\S]{0,160}?(?:post[- ]year[- ]end|subsequent|after year[- ]end)", re.I)

@dataclass(frozen=True)
class Passage:
    id: str
    start: int
    end: int
    text: str
    heading: str
    topics: frozenset[str]
    critical: bool

    def payload(self) -> dict:
        return {"id": self.id, "heading": self.heading, "text": self.text}

@dataclass(frozen=True)
class Selection:
    passages: tuple[Passage, ...]
    source_characters: int
    selected_characters: int
    source_bytes: int
    selected_bytes: int
    total_passages: int

    @property
    def reduced(self) -> bool:
        return len(self.passages) < self.total_passages

    def record(self) -> dict:
        return {"source_characters": self.source_characters,
                "selected_characters": self.selected_characters,
                "source_bytes": self.source_bytes, "selected_bytes": self.selected_bytes,
                "passages": len(self.passages), "total_passages": self.total_passages,
                "reduced": self.reduced, "limit_bytes": MAX_EXCERPT_BYTES}


def split_passages(text: str) -> list[Passage]:
    # Recognise short headings but keep all other text, including tables, in order.
    headings = []
    for m in re.finditer(r"(?m)^[^\n]+$", text):
        line = m[0].strip()
        if len(line) <= 95 and "\t" not in m[0] and HEADING.search(line) and not re.search(r"[.;]$|£|\$|€|%", line):
            next_line = re.search(r"\S[^\n]*", text[m.end():m.end()+100])
            table_cell = next_line and re.fullmatch(r"[+−-]?[£$€]?\(?\d[\d,]*(?:\.\d+)?\)?\s*(?:%|bps|p|m|k|bn)?", next_line[0].strip(), re.I)
            # e.g. Contract housing\n5.1 is a table row, not a contract heading.
            if not (table_cell and re.search(r"housing|revenue|profit|margin|per share",line,re.I)):
                headings.append((m.start(), line))
    boundaries = [0] + [p for p, _ in headings if p > 0] + [len(text)]
    critical_spans = [(m.start(), m.end()) for m in CRITICAL.finditer(text)]
    chunks = []
    for start, end in zip(boundaries, boundaries[1:]):
        heading = next((s for p, s in reversed(headings) if p <= start), "Announcement")
        at = start
        while at < end:
            stop = min(end, at + BLOCK_CHARS)
            if stop < end:
                # Prefer complete paragraphs/rows, then sentences, then word boundaries.
                low = at + BLOCK_CHARS // 2
                cuts = [m.end() for m in re.finditer(r"\n\s*\n|[.!?]\s+|\n", text[low:stop])]
                if cuts:
                    stop = low + cuts[-1]
                else:
                    cut = text.rfind(" ", low, stop)
                    if cut >= low: stop = cut + 1
            chunk = text[at:stop]
            if chunk.strip():
                topics = frozenset(k for k, rx in PATTERNS.items() if rx.search(heading + "\n" + chunk))
                chunks.append(Passage(f"p{len(chunks)}", at, stop, chunk, heading, topics,
                                      any(a < stop and b > at for a, b in critical_spans)))
            at = stop
    return chunks


def select_passages(text: str, *, max_bytes: int = MAX_EXCERPT_BYTES) -> Selection:
    if not 8_000 <= max_bytes <= MAX_EXCERPT_BYTES:
        raise CardError("CARD_SELECTION")
    passages = split_passages(text)
    if not passages: raise CardError("CARD_SELECTION")
    chosen: dict[str, Passage] = {}
    used = 0

    def add(p: Passage, *, required: bool = False) -> None:
        nonlocal used
        if p.id in chosen: return
        size = len(p.text.encode("utf-8")) + len(p.heading.encode("utf-8"))
        if used + size > max_bytes or len(chosen) >= MAX_PASSAGES:
            if required: raise CardError("CARD_SELECTION")
            return
        chosen[p.id] = p
        used += size

    if sum(len(p.text.encode("utf-8")) + len(p.heading.encode("utf-8")) for p in passages) <= max_bytes and len(passages) <= MAX_PASSAGES:
        for p in passages: add(p, required=True)
    else:
        add(passages[0], required=True)
        # Reserve risk and subsequent-payment context before spending on headline figures.
        for p in passages:
            if p.critical: add(p, required=True)
        # Cover present sections throughout the document, not only its opening.
        for topic in ("highlights", "outlook", "financial", "capital", "risk", "subsequent", "commercial"):
            candidates = [p for p in passages if topic in p.topics]
            if candidates:
                best = max(candidates, key=lambda p: (bool(re.search(r"£|\$|€|\d+%", p.text)), -p.start))
                add(best, required=True)
        # Keep table/unit/column context adjacent to chosen chunks where possible.
        anchors = set(chosen)
        for i, p in enumerate(passages):
            if p.id in anchors:
                if i and passages[i-1].heading == p.heading: add(passages[i-1])
                if i+1 < len(passages) and passages[i+1].heading == p.heading: add(passages[i+1])
        for p in sorted(passages, key=lambda p: (-len(p.topics), p.start)):
            if p.topics: add(p)
    selected = tuple(sorted(chosen.values(), key=lambda p: p.start))
    return Selection(selected, len(text), sum(len(p.text) for p in selected),
                     len(text.encode("utf-8")), used, len(passages))
