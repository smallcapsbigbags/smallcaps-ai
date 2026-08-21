from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, Sequence

from analyst.models import AnalystNote, AnnouncementInput


class AnalystEngine(Protocol):
    model_name: str

    def analyse(
        self,
        announcement: AnnouncementInput,
        prior_context: Sequence[dict[str, object]],
    ) -> AnalystNote: ...


class OpenAIAnalystEngine:
    """Structured OpenAI analyst engine adapted from the RNS-Xray analyser.

    Pass 1 deliberately keeps one inference call per material announcement. The call
    returns both atomic facts and the Analyst Note contract; Pass 2 will benchmark and
    refine the research prompt rather than changing persistence again.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        prompt_path: Path | None = None,
        timeout_seconds: int = 180,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for live analysis")
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self.model_name = model
        self.prompt_path = prompt_path or (
            Path(__file__).resolve().parents[1] / "prompts" / "FOUNDATION_ANALYST.md"
        )
        self.system_prompt = self.prompt_path.read_text(encoding="utf-8")

    def analyse(
        self,
        announcement: AnnouncementInput,
        prior_context: Sequence[dict[str, object]],
    ) -> AnalystNote:
        payload = {
            "announcement": announcement.model_dump(mode="json"),
            "eligible_prior_context": list(prior_context),
        }
        response = self.client.responses.parse(
            model=self.model_name,
            instructions=self.system_prompt,
            input=(
                "Analyse the supplied UK regulatory announcement using only the source "
                "and eligible prior context. Return the required structured AnalystNote.\n\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
            text_format=AnalystNote,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("OpenAI returned no structured AnalystNote")
        if parsed.source_id != announcement.source_id:
            raise RuntimeError(
                "OpenAI did not preserve source_id: "
                f"expected {announcement.source_id!r}, got {parsed.source_id!r}"
            )
        return parsed
