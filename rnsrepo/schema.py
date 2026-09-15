"""Only the words and figures needed by a card, with short source quotations."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

VERSION = "rnsrepo-card-1"

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class Reference(StrictModel):
    passage_id: str = Field(min_length=1, max_length=12)
    quote: str = Field(min_length=12, max_length=900)

class Statement(StrictModel):
    text: str = Field(min_length=1, max_length=700)
    evidence: list[Reference] = Field(min_length=1, max_length=4)

class Metric(StrictModel):
    label: str = Field(min_length=1, max_length=65)
    value: str = Field(min_length=1, max_length=40)
    period: str = Field(max_length=90)
    note: str = Field(max_length=220)
    evidence: list[Reference] = Field(min_length=1, max_length=4)

class CardDraft(StrictModel):
    announcement_type: Literal["Results", "Trading update", "Contract", "Fundraising",
                               "Acquisition", "Director dealing", "Other"]
    headline: Statement
    supporting_sentence: Statement
    metrics: list[Metric] = Field(max_length=4)
    what_changed: Statement | None
    qualification: Statement | None

# Local code accepts only these public codes; never return/log provider error bodies.
ERRORS = frozenset({"CARD_CONFIGURATION", "CARD_RATE_LIMIT", "CARD_QUOTA", "CARD_TIMEOUT",
    "CARD_PROVIDER", "CARD_INCOMPLETE", "CARD_REFUSED", "CARD_FORMAT", "CARD_EVIDENCE",
    "CARD_SELECTION", "CARD_REQUEST_LIMIT"})

class CardError(RuntimeError):
    def __init__(self, code: str, *, findings: tuple[str, ...] = ()) -> None:
        self.code = code if code in ERRORS else "CARD_PROVIDER"
        self.findings = tuple(c for c in findings if c.isupper() and c.replace("_", "").isalnum())[:16]
        super().__init__(self.code)
