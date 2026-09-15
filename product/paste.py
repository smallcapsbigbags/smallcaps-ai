"""Source-scoped contract for the on-demand MVP. No network or database access."""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

from product.paste_card import CARD_LAYOUT_VERSION, select_metric_indexes

if TYPE_CHECKING:
    from analyst.models import AnalystNote

MIN_PASTE_CHARS = 120
MAX_PASTE_CHARS = 120_000
PASTE_CONTRACT_VERSION = "paste-mvp-2"


class PasteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=MIN_PASTE_CHARS, max_length=MAX_PASTE_CHARS)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(value) < MIN_PASTE_CHARS:
            raise ValueError("Paste the announcement text, including its header.")
        if "\x00" in value:
            raise ValueError("Paste plain text, not a binary document.")
        if re.fullmatch(r"https?://\S+", value):
            raise ValueError("Paste the announcement text, not a link.")
        if re.search(r"<(?:!doctype|html|body)\b", value, re.I):
            raise ValueError("Paste the readable announcement, not page HTML.")
        if len(re.findall(r"(?im)^\s*RNS\s+Number\s*:", value)) > 1:
            raise ValueError("Paste one announcement at a time.")
        return value

    @property
    def source_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def source_id(self) -> str:
        return f"urn:smallcaps:paste:{self.source_hash}"


class PasteIdentity(BaseModel):
    company: str | None = None
    ticker: str | None = None
    publication_date: date | None = None
    title: str = "Pasted announcement"


_MONTHS = {name.lower(): i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"), 1)}
_MONTHS.update({name[:3]: value for name, value in list(_MONTHS.items())})
_DATE_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})$")
_COMPANY_RE = re.compile(r"^[\w][\w &.,'’()/-]{1,100}\b(?:plc|limited|ltd\.?)$", re.I)
_TICKER_RE = re.compile(r"\b(?:AIM|LSE|ticker)\s*:\s*([A-Z0-9][A-Z0-9.-]{0,9})\b")
_TITLE_RE = re.compile(
    r"^(?:(?:final|interim|annual|full[- ]year|half[- ]year) results|"
    r"trading update|contract (?:award|win)|operational update|"
    r"(?:proposed )?(?:placing|acquisition)|fundraising|profit warning)\b", re.I)


def extract_identity(text: str) -> PasteIdentity:
    """Conservative header parsing. Missing or ambiguous metadata stays missing."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = lines[:12]
    company = next((line for line in header if _COMPANY_RE.fullmatch(line)), None)
    dates: set[date] = set()
    for line in header:
        match = _DATE_RE.fullmatch(line)
        if match and match[2].lower() in _MONTHS:
            try:
                dates.add(date(int(match[3]), _MONTHS[match[2].lower()], int(match[1])))
            except ValueError:
                pass
    tickers = set(_TICKER_RE.findall(text[:4000]))
    title = next((line for line in lines[:25] if _TITLE_RE.search(line)), "Pasted announcement")
    return PasteIdentity(
        company=company,
        ticker=next(iter(tickers)) if len(tickers) == 1 else None,
        publication_date=next(iter(dates)) if len(dates) == 1 else None,
        title=title[:180],
    )


def project_paste_result(source: PasteRequest, note: AnalystNote) -> dict[str, object]:
    """Project a card without rewriting source facts or trimming their qualifications.

    Metric indexes select highlights only. Every original fact stays in `facts`;
    the renderer shows the remainder in More facts and all warnings in What matters.
    """
    if note.source_id != source.source_id:
        raise ValueError("Analysis does not match the supplied document.")
    identity = extract_identity(source.text)
    facts = [fact.model_dump(mode="json") for fact in note.key_facts]
    matters = [*note.challenges_case]
    if note.disclosure_assessment.note:
        matters.append(note.disclosure_assessment.note)
    if note.disclosure_assessment.missing_items:
        matters.append("Not disclosed: " + "; ".join(note.disclosure_assessment.missing_items))
    matters.extend(note.source_warnings)
    matters = list(dict.fromkeys(item.strip() for item in matters if item.strip()))
    return {
        "schema_version": PASTE_CONTRACT_VERSION,
        "card_layout_version": CARD_LAYOUT_VERSION,
        "source_hash": source.source_hash,
        "source_kind": "user-paste",
        "source_verified": False,
        "identity": identity.model_dump(mode="json"),
        "rns_type": note.rns_type,
        "headline": note.headline,
        "summary": note.takeaway,
        "facts": facts,
        "metric_indexes": select_metric_indexes(facts, note.rns_type),
        "what_changed": note.what_changed.today,
        "analyst_view": note.analyst_view,
        "what_matters": matters,
        "direction": note.impact_colour,
        "materiality": note.impact_score,
        "materiality_rationale": note.impact_rationale,
        "coverage_status": "building",
    }
