from __future__ import annotations

from analyst.version import DEFAULT_PROMPT_VERSION
from settings import Settings


_RAILWAY_VARIABLES = (
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_ENVIRONMENT_ID",
    "RAILWAY_PROJECT_ID",
    "RAILWAY_SERVICE_ID",
)


def _clear_railway(monkeypatch) -> None:
    for name in _RAILWAY_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_railway_ignores_stale_prompt_version(monkeypatch) -> None:
    _clear_railway(monkeypatch)
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "project-test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/smallcaps")
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")
    monkeypatch.setenv("PROMPT_VERSION", "analyst-engine-stale")

    settings = Settings.from_env()
    _errors, warnings = settings.runtime_issues("web")

    assert settings.running_on_railway
    assert settings.prompt_version == DEFAULT_PROMPT_VERSION
    assert any("is ignored on Railway" in warning for warning in warnings)


def test_local_benchmark_can_override_prompt_version(monkeypatch) -> None:
    _clear_railway(monkeypatch)
    monkeypatch.setenv("PROMPT_VERSION", "local-benchmark-candidate")

    settings = Settings.from_env()

    assert not settings.running_on_railway
    assert settings.prompt_version == "local-benchmark-candidate"
