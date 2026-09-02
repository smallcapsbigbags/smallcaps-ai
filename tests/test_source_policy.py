from __future__ import annotations

from ingestion.source_policy import (
    AIMSourcePolicy,
    normalise_aim_discovery_mode,
)
from settings import Settings


def test_discovery_mode_aliases_are_normalised() -> None:
    assert normalise_aim_discovery_mode("owner_test") == "owner-test"
    assert normalise_aim_discovery_mode("licensed-feed") == "licensed"
    assert normalise_aim_discovery_mode("") == "disabled"


def test_disabled_mode_fails_closed_without_an_error() -> None:
    policy = AIMSourcePolicy(mode="disabled")
    errors, warnings = policy.issues()

    assert errors == []
    assert warnings
    assert not policy.enabled
    assert not policy.public_launch_ready


def test_owner_test_requires_private_beta_and_explicit_acknowledgement() -> None:
    policy = AIMSourcePolicy(mode="owner-test")
    errors, warnings = policy.issues()

    assert len(errors) == 2
    assert any("PRIVATE_BETA_MODE=true" in item for item in errors)
    assert any("ALLOW_UNLICENSED_OWNER_TEST_CATALOGUES=true" in item for item in errors)
    assert any("not approved for a public or commercial launch" in item for item in warnings)


def test_owner_test_is_valid_only_inside_private_beta() -> None:
    policy = AIMSourcePolicy(
        mode="owner-test",
        private_beta_mode=True,
        allow_unlicensed_owner_test_catalogues=True,
    )
    errors, warnings = policy.issues()

    assert errors == []
    assert warnings
    assert policy.enabled
    assert not policy.public_launch_ready


def test_licensed_mode_requires_a_secure_feed() -> None:
    missing = AIMSourcePolicy(mode="licensed")
    insecure = AIMSourcePolicy(
        mode="licensed",
        licensed_feed_url="http://example.com/feed",
    )
    valid = AIMSourcePolicy(
        mode="licensed",
        licensed_feed_url="https://vendor.example/aim.json",
    )

    assert missing.issues()[0]
    assert insecure.issues()[0]
    assert valid.issues() == ([], [])
    assert valid.public_launch_ready


def test_settings_runtime_gate_blocks_public_owner_test(monkeypatch) -> None:
    monkeypatch.setenv("AIM_DISCOVERY_MODE", "owner-test")
    monkeypatch.setenv("ALLOW_UNLICENSED_OWNER_TEST_CATALOGUES", "true")
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("APP_BETA_PASSWORD", "test")

    settings = Settings.from_env()
    errors, _warnings = settings.runtime_issues("ingestion")

    assert any("permitted only while PRIVATE_BETA_MODE=true" in item for item in errors)


def test_disabled_ingestion_does_not_require_openai_key(monkeypatch) -> None:
    monkeypatch.setenv("AIM_DISCOVERY_MODE", "disabled")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")

    settings = Settings.from_env()
    errors, warnings = settings.runtime_issues("ingestion")

    assert not any("OPENAI_API_KEY" in item for item in errors)
    assert any("AIM discovery is disabled" in item for item in warnings)
