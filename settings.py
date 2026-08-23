from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from analyst.version import DEFAULT_PROMPT_VERSION


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _watchlist(value: str) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for item in value.split(","):
        ticker = item.upper().strip().replace(".L", "").rstrip(".-")
        if ticker and ticker not in seen:
            seen.add(ticker)
            output.append(ticker)
    return tuple(output)


def _running_on_railway() -> bool:
    return any(
        os.getenv(name)
        for name in (
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_ENVIRONMENT_ID",
            "RAILWAY_PROJECT_ID",
            "RAILWAY_SERVICE_ID",
        )
    )


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
    app_beta_password: str
    private_beta_mode: bool
    market_data_enabled: bool
    market_data_timeout_seconds: int
    default_watchlist: tuple[str, ...]
    root_dir: Path
    running_on_railway: bool

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(__file__).resolve().parent
        railway = _running_on_railway()
        configured_prompt_version = os.getenv("PROMPT_VERSION", "").strip()

        # Production deployments must record the prompt version shipped with the
        # code. A stale Railway variable must not silently label current analyst
        # output as an older engine. Local/one-off benchmark runs may still override it.
        prompt_version = (
            DEFAULT_PROMPT_VERSION
            if railway
            else configured_prompt_version or DEFAULT_PROMPT_VERSION
        )

        return cls(
            database_url=os.getenv(
                "DATABASE_URL", "sqlite+pysqlite:///data/smallcaps.db"
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            openai_deep_model=os.getenv("OPENAI_DEEP_MODEL", "gpt-5.4"),
            openai_max_output_tokens=max(
                2000,
                int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "12000") or "12000"),
            ),
            prompt_version=prompt_version,
            deep_search_batch_size=max(
                1, int(os.getenv("DEEP_SEARCH_BATCH_SIZE", "5") or "5")
            ),
            max_document_chars=max(
                5000, int(os.getenv("MAX_DOCUMENT_CHARS", "45000") or "45000")
            ),
            min_evidence_chars=max(
                1, int(os.getenv("MIN_EVIDENCE_CHARS", "40") or "40")
            ),
            investegate_aim_max_pages=max(
                1, int(os.getenv("INVESTEGATE_AIM_MAX_PAGES", "8") or "8")
            ),
            max_ai_items=max(
                3, int(os.getenv("MAX_AI_ITEMS", "36") or "36")
            ),
            app_admin_password=os.getenv("APP_ADMIN_PASSWORD", ""),
            app_beta_password=os.getenv("APP_BETA_PASSWORD", ""),
            private_beta_mode=_env_bool("PRIVATE_BETA_MODE", railway),
            market_data_enabled=_env_bool("MARKET_DATA_ENABLED", True),
            market_data_timeout_seconds=max(
                5,
                int(os.getenv("MARKET_DATA_TIMEOUT_SECONDS", "25") or "25"),
            ),
            default_watchlist=_watchlist(os.getenv("DEFAULT_WATCHLIST", "")),
            root_dir=root,
            running_on_railway=railway,
        )

    @property
    def uses_postgres(self) -> bool:
        value = self.database_url.lower().strip()
        return value.startswith("postgres://") or value.startswith("postgresql")

    def runtime_issues(self, service: str) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        if self.running_on_railway and not self.uses_postgres:
            errors.append(
                "Railway must use a PostgreSQL DATABASE_URL; SQLite is ephemeral."
            )
        if self.private_beta_mode and not self.app_beta_password:
            errors.append("PRIVATE_BETA_MODE requires APP_BETA_PASSWORD.")
        if service in {"ingestion", "benchmark"} and not self.openai_api_key:
            errors.append(f"{service} requires OPENAI_API_KEY.")
        if service == "prices" and not self.market_data_enabled:
            errors.append("Price service is disabled by MARKET_DATA_ENABLED=false.")
        if service in {"web", "ingestion"} and not self.app_admin_password:
            warnings.append(
                "APP_ADMIN_PASSWORD is unset; the Analyst QA route is disabled."
            )

        configured_prompt_version = os.getenv("PROMPT_VERSION", "").strip()
        if (
            self.running_on_railway
            and configured_prompt_version
            and configured_prompt_version != DEFAULT_PROMPT_VERSION
        ):
            warnings.append(
                f"PROMPT_VERSION={configured_prompt_version!r} is ignored on Railway; "
                f"the code-locked version {DEFAULT_PROMPT_VERSION!r} is used."
            )
        return errors, warnings
