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
    prompt_version: str
    root_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parent
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite+pysqlite:///data/smallcaps.db"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            prompt_version=os.getenv("PROMPT_VERSION", DEFAULT_PROMPT_VERSION),
            root_dir=root,
        )
