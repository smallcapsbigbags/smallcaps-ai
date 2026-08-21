from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from analyst.version import DEFAULT_PROMPT_VERSION


@dataclass(frozen=True)
class Settings:
    database_url: str
    openai_api_key: str
    openai_model: str
    openai_deep_model: str
    openai_max_output_tokens: int
    prompt_version: str
    deep_search_batch_size: int
    max_document_chars: int
    min_evidence_chars: int
    investegate_aim_max_pages: int
    max_ai_items: int
    app_admin_password: str
    root_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parent
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "sqlite+pysqlite:///data/smallcaps.db",
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            openai_deep_model=os.getenv("OPENAI_DEEP_MODEL", "gpt-5.4"),
            openai_max_output_tokens=max(
                2_000,
                int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "12000") or "12000"),
            ),
            prompt_version=os.getenv(
                "PROMPT_VERSION", DEFAULT_PROMPT_VERSION
            ),
            deep_search_batch_size=max(
                1, int(os.getenv("DEEP_SEARCH_BATCH_SIZE", "5") or "5")
            ),
            max_document_chars=max(
                5_000,
                int(os.getenv("MAX_DOCUMENT_CHARS", "45000") or "45000"),
            ),
            min_evidence_chars=max(
                1,
                int(os.getenv("MIN_EVIDENCE_CHARS", "40") or "40"),
            ),
            investegate_aim_max_pages=max(
                1,
                int(os.getenv("INVESTEGATE_AIM_MAX_PAGES", "8") or "8"),
            ),
            max_ai_items=max(
                3, int(os.getenv("MAX_AI_ITEMS", "36") or "36")
            ),
            app_admin_password=os.getenv("APP_ADMIN_PASSWORD", ""),
            root_dir=root,
        )
