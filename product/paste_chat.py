"""Text-only follow-ups. Clients never supply source, analysis or conversation history."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from analyst.models import StrictModel
from analyst.paste_evidence import EvidenceFact

CHAT_VERSION = "paste-chat-4"
MAX_QUESTION_CHARS = 2_000
MAX_TURNS = 8


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=3, max_length=MAX_QUESTION_CHARS)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,80}$")
    turn_index: int = Field(ge=0, le=MAX_TURNS)

    @field_validator("question")
    @classmethod
    def plain_question(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(value) < 3 or "\x00" in value:
            raise ValueError("Ask a question about this announcement.")
        return value


class AnswerParagraph(StrictModel):
    text: str = Field(min_length=1, max_length=1_200)
    kind: Literal["source", "interpretation", "general", "limitation"]
    quotes: list[str] = Field(default_factory=list, max_length=6)
    fact_indexes: list[int] = Field(default_factory=list, max_length=8)


class FollowupAnswer(StrictModel):
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    scope: Literal["answered", "needs_context", "outside_scope"]
    paragraphs: list[AnswerParagraph] = Field(min_length=1, max_length=4)
    calculations: list[EvidenceFact] = Field(default_factory=list, max_length=2)
