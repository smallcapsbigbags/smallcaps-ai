from __future__ import annotations

import threading
import time
from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.frontend import _token, create_frontend_routes
from api.paste import create_paste_routes
from api.paste_jobs import BusyError, PasteJobs
from product.paste import PasteRequest, extract_identity, project_paste_result

TRT = """RNS Number : 7173U
Transense Technologies PLC
15 September 2026

Contract award with Continental to develop next-generation tyre management tool
Transense has secured a funded six month development and supply contract with Continental.
Following successful completion, production is expected from Q2 2027.
The board expects annual revenues of more than £0.7m from future deployments,
subject to successful completion of the development project.
"""
HEADERS = {"X-Smallcaps-Action": "analyse", "Origin": "http://testserver"}


def wait_for(jobs: PasteJobs, owner: str, job_id: str) -> dict:
    for _ in range(200):
        item = jobs.get(owner, job_id)
        if item and item["status"] != "processing":
            return item
        time.sleep(.01)
    raise AssertionError("test job did not finish")


def test_source_normalisation_preserves_numbers_and_line_structure():
    source = PasteRequest(text=TRT.replace("\n", "\r\n"))
    assert source.text == TRT.strip()
    assert source.source_hash == PasteRequest(text=TRT).source_hash
    assert "more than £0.7m" in source.text
    assert "\n\n" in source.text


@pytest.mark.parametrize("text", [
    "hello", " " * 150, "x" * 120001, "https://example.com/" + "a" * 140,
    "<html>" + "a" * 140, TRT + "\nRNS Number : 1234A\nAnother announcement",
    TRT + "\x00", 123, None,
])
def test_invalid_pastes_rejected(text):
    with pytest.raises(ValidationError):
        PasteRequest(text=text)


def test_unknown_fields_cannot_override_identity_or_status():
    with pytest.raises(ValidationError):
        PasteRequest(text=TRT, source_verified=True)


def test_metadata_is_parsed_only_when_supported():
    identity = extract_identity(TRT)
    assert identity.company == "Transense Technologies PLC"
    assert identity.publication_date == date(2026, 9, 15)
    assert identity.ticker is None  # The pasted text does not supply TRT.
    assert extract_identity(TRT + " (AIM: TRT)").ticker == "TRT"
    assert extract_identity(TRT + " (AIM: TRT) and (AIM: SPR)").ticker is None
    unknown = extract_identity("At 31 May 2026, net cash was £1.2m. " * 5)
    assert unknown.publication_date is None
    assert unknown.company is None
    assert extract_identity(TRT.replace("15 September", "31 February")).publication_date is None


def _note(source: PasteRequest):
    from analyst.models import AnalystNote, KeyFact, WhatChanged
    return AnalystNote(
        source_id=source.source_id, rns_type="Contracts", impact_colour="green",
        impact_score=2, impact_level="medium", impact_rationale="A funded development programme adds a conditional revenue opportunity.",
        headline="Continental funds tyre-tool development",
        takeaway="Production is expected from Q2 2027 following successful development. Future deployments are expected to generate more than £0.7m annual revenue.",
        key_facts=[KeyFact(
            label="Expected annual revenue", value=">£0.7m", basis="reported",
            note="Subject to successful development and subsequent deployment.",
            metric="expected annual revenue", period="Future deployments", unit="million", currency="GBP",
        )],
        what_changed=WhatChanged(before="No independent prior history supplied.",
            today="Continental has awarded a funded development and supply programme.",
            read_through="Revenue depends on completing development and future deployments."),
        analyst_view="Useful commercial progress, but revenue is conditional on successful development and deployment. Margin and minimum purchase volumes are not disclosed.",
        challenges_case=["Future revenue depends on successful development and subsequent deployment."],
        source_references=[source.source_id], confidence=.95,
    )


def test_projection_preserves_conditions_periods_and_full_text():
    source = PasteRequest(text=TRT)
    note = _note(source)
    note.takeaway = " ".join(["Context."] * 50) + " Revenue remains conditional."
    result = project_paste_result(source, note)
    assert result["summary"].endswith("Revenue remains conditional.")
    assert result["facts"][0]["note"] == note.key_facts[0].note
    assert result["facts"][0]["period"] == "Future deployments"
    assert result["facts"][0]["unit"] == "million"
    assert result["facts"][0]["currency"] == "GBP"
    assert result["source_verified"] is False
    assert result["identity"]["ticker"] is None
    assert result["coverage_status"] == "building"
    note.source_id = "another-document"
    with pytest.raises(ValueError):
        project_paste_result(source, note)


def test_paste_adapter_does_not_fabricate_a_publication_timestamp():
    from analyst.paste import build_pasted_announcement
    announcement = build_pasted_announcement(PasteRequest(text=TRT))
    assert announcement.published_at is None
    assert announcement.publication_date == "2026-09-15"
    assert announcement.ticker == "UNKNOWN"
    assert announcement.source_kind == "user-paste"
    assert announcement.source_url.startswith("urn:smallcaps:paste:")


def test_adapter_reuses_engine_and_checks_quality_without_history(monkeypatch):
    import analyst.paste as adapter
    from analyst.models import QualityReport
    source = PasteRequest(text=TRT)
    calls = []
    client = SimpleNamespace(close=lambda: calls.append("closed"))
    class Engine:
        def __init__(self, **kwargs):
            self.client = client
            self.model_name = kwargs["model"]
            self.system_prompt = "core"
            self.review_prompt = "review"
        def analyse(self, announcement, prior_context):
            calls.append((announcement, prior_context, self.system_prompt, self.review_prompt))
            return _note(source)
    monkeypatch.setattr(adapter, "OpenAIAnalystEngine", Engine)
    monkeypatch.setattr(adapter.Settings, "from_env", lambda: SimpleNamespace(
        openai_api_key="test-only", openai_model="test-model", openai_max_output_tokens=2000, prompt_version="test-prompt"))
    monkeypatch.setattr(adapter, "assess_analysis_quality", lambda *a, **kw: QualityReport(status="publishable"))
    result = adapter.analyse_paste(source)
    assert result["versions"]["model"] == "test-model"
    assert calls[0][1] == ()
    assert "ON-DEMAND SOURCE BOUNDARY" in calls[0][2]
    assert "ON-DEMAND SOURCE BOUNDARY" in calls[0][3]
    assert calls[-1] == "closed"
    monkeypatch.setattr(adapter, "assess_analysis_quality", lambda *a, **kw: QualityReport(
        status="blocked", flags=[{"code": "TEST", "severity": "block", "message": "Not safe"}]))
    with pytest.raises(adapter.PasteQualityError):
        adapter.analyse_paste(source)
    assert calls[-1] == "closed"


def test_jobs_dedupe_isolate_and_expire():
    now = [0.0]
    calls = []
    jobs = PasteJobs(lambda source: calls.append(source.source_hash) or {"headline": "Test"}, clock=lambda: now[0], ttl=10)
    try:
        source = PasteRequest(text=TRT)
        first = jobs.submit("owner-a", source)
        wait_for(jobs, "owner-a", first["analysis_id"])
        second = jobs.submit("owner-a", source)
        assert first["analysis_id"] == second["analysis_id"]
        assert len(calls) == 1
        assert jobs.get("owner-b", first["analysis_id"]) is None
        now[0] = 11
        assert jobs.get("owner-a", first["analysis_id"]) is None
    finally:
        jobs.close()


def test_busy_jobs_do_not_queue_more_paid_work():
    release = threading.Event()
    jobs = PasteJobs(lambda source: release.wait(3) or {}, max_active=1)
    try:
        jobs.submit("a", PasteRequest(text=TRT))
        with pytest.raises(BusyError):
            jobs.submit("b", PasteRequest(text=TRT))
    finally:
        release.set()
        jobs.close()


def test_owner_and_global_caps_are_enforced():
    jobs = PasteJobs(lambda source: {}, owner_limit=1, hourly_limit=2)
    try:
        first = jobs.submit("a", PasteRequest(text=TRT))
        wait_for(jobs, "a", first["analysis_id"])
        with pytest.raises(BusyError):
            jobs.submit("a", PasteRequest(text=TRT + " Additional disclosure."))
        second = jobs.submit("b", PasteRequest(text=TRT))
        wait_for(jobs, "b", second["analysis_id"])
        with pytest.raises(BusyError):
            jobs.submit("c", PasteRequest(text=TRT))
    finally:
        jobs.close()


def test_provider_failures_are_sanitised_and_not_automatically_retried(caplog):
    calls = []
    def fail(source):
        calls.append(1)
        raise RuntimeError("SECRET-KEY private source text")
    jobs = PasteJobs(fail)
    try:
        first = jobs.submit("a", PasteRequest(text=TRT))
        payload = wait_for(jobs, "a", first["analysis_id"])
        jobs.submit("a", PasteRequest(text=TRT))
        assert payload["status"] == "failed"
        assert payload["result"] is None
        assert "SECRET" not in str(payload) + caplog.text
        assert len(calls) == 1
    finally:
        jobs.close()


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("PASTE_ANALYSIS_ENABLED", "true")
    calls = []
    jobs = PasteJobs(lambda source: calls.append(source.text) or {"headline": "Test"})
    settings = SimpleNamespace(private_beta_mode=True, app_beta_password="test-secret", openai_api_key="test-only")
    app = Starlette(routes=create_paste_routes(lambda: jobs, lambda: settings))
    client = TestClient(app)
    client.cookies.set("smallcaps_beta", _token(settings.app_beta_password))
    yield client, app, settings, calls
    client.close()
    jobs.close()


def test_api_requires_beta_auth_and_does_not_enable_anonymous_paid_access(api):
    client, app, settings, calls = api
    client.cookies.clear()
    assert client.post("/api/v1/analyse", json={"text": TRT}, headers=HEADERS).status_code == 401
    settings.private_beta_mode = False
    assert client.post("/api/v1/analyse", json={"text": TRT}, headers=HEADERS).status_code == 503
    assert calls == []


def test_prepare_does_not_call_analyst_and_sets_private_cookie(api):
    client, app, settings, calls = api
    response = client.get("/api/v1/analyse")
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert calls == []


@pytest.mark.parametrize("headers", [
    {"Origin": "https://attacker.invalid", "X-Smallcaps-Action": "analyse"},
    {"Origin": "null", "X-Smallcaps-Action": "analyse"}, {},
])
def test_api_rejects_cross_site_or_missing_action_header(api, headers):
    client, app, settings, calls = api
    assert client.post("/api/v1/analyse", json={"text": TRT}, headers=headers).status_code == 403
    assert calls == []


def test_api_invalid_input_and_oversized_body_never_start_model(api):
    client, app, settings, calls = api
    assert client.post("/api/v1/analyse", json={"text": "short"}, headers=HEADERS).status_code == 422
    assert client.post("/api/v1/analyse", content="{}", headers=HEADERS).status_code == 415
    headers = {**HEADERS, "Content-Type": "application/json"}
    assert client.post("/api/v1/analyse", content=b"x" * 520001, headers=headers).status_code == 413
    assert client.post("/api/v1/analyse", content=b"{", headers=headers).status_code == 422
    assert calls == []


def test_api_duplicate_submission_and_cross_browser_privacy(api):
    client, app, settings, calls = api
    client.get("/api/v1/analyse")
    first = client.post("/api/v1/analyse", json={"text": TRT}, headers=HEADERS)
    second = client.post("/api/v1/analyse", json={"text": TRT}, headers=HEADERS)
    job_id = first.json()["analysis_id"]
    assert second.json()["analysis_id"] == job_id
    for _ in range(100):
        response = client.get(f"/api/v1/analyse/{job_id}")
        if response.json()["status"] == "complete":
            break
        time.sleep(.01)
    assert response.json()["status"] == "complete"
    assert response.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in response.headers
    assert calls == [TRT.strip()]
    with TestClient(app) as other:
        other.cookies.set("smallcaps_beta", _token(settings.app_beta_password))
        assert other.get(f"/api/v1/analyse/{job_id}").status_code == 404


def test_home_is_minimal_and_existing_news_route_survives(monkeypatch):
    monkeypatch.setenv("PRIVATE_BETA_MODE", "false")
    with TestClient(Starlette(routes=create_frontend_routes())) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "See what matters." in home.text
        assert "Paste an RNS…" in home.text
        assert 'id="analyse-form"' in home.text
        assert "primary-nav" not in home.text
        assert "/assets/research.js" not in home.text
        assert "maxlength=" not in home.text  # Do not silently truncate pasted documents.
        assert 'id="monitoring-sheet"' in client.get("/rns").text
