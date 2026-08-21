from settings import Settings


def test_railway_rejects_ephemeral_sqlite(monkeypatch) -> None:
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "project"); monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///data/local.db"); monkeypatch.setenv("APP_BETA_PASSWORD", "secret")
    errors, _warnings = Settings.from_env().runtime_issues("web")
    assert any("PostgreSQL" in error for error in errors)


def test_private_beta_requires_password(monkeypatch) -> None:
    monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False); monkeypatch.setenv("PRIVATE_BETA_MODE", "true"); monkeypatch.delenv("APP_BETA_PASSWORD", raising=False)
    errors, _warnings = Settings.from_env().runtime_issues("web")
    assert any("APP_BETA_PASSWORD" in error for error in errors)


def test_ingestion_requires_openai_key(monkeypatch) -> None:
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false"); monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    errors, _warnings = Settings.from_env().runtime_issues("ingestion")
    assert any("OPENAI_API_KEY" in error for error in errors)
