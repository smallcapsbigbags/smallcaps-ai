"""Pass 4 evidence, cost-boundary, session isolation and API tests. No paid model."""
from __future__ import annotations

import copy
import json
import sys
import threading
import time
from types import SimpleNamespace
from pathlib import Path

import pytest
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.testclient import TestClient

from analyst.paste_chat import FollowupQualityError, answer_question, validate_answer
from api.frontend import _token
from api.paste import create_paste_routes
from api.paste_jobs import BusyError, PasteJobs
from api.paste_conversations import ConversationConflict, ConversationMissing, FollowupJobs
from api.paste_questions import create_question_routes
from jobs.paste_chat_cases import example
from product.paste_chat import FollowupAnswer, QuestionRequest
from product.paste import PasteRequest


def question(text="Is this revenue guaranteed?", i=0, rid=None):
    return QuestionRequest(question=text, request_id=rid or f"question-request-{i:04}", turn_index=i)


def wait(fn):
    for _ in range(300):
        result = fn()
        if result["status"] != "processing":
            return result
        time.sleep(.005)
    raise AssertionError("job did not finish")


@pytest.mark.parametrize("name", ["spr", "trt"])
def test_supported_answers_preserve_natural_copy_and_source_spans(name):
    source, card, answer = example(name)
    result = validate_answer(source, card, answer)
    assert result["paragraphs"] == [p.text for p in answer.paragraphs]
    assert result["source_verified"] is False
    for anchor in result["sources"]:
        assert source.text[anchor["start"]:anchor["end"]] == anchor["quote"]


@pytest.mark.parametrize("mutation", ["source", "fake-quote", "bad-index", "number", "bound", "expected", "condition", "no-support", "external-link", "guaranteed"])
def test_corrupted_answers_are_rejected(mutation):
    source, card, answer = example()
    p = answer.paragraphs[0]
    if mutation == "source": answer.source_hash = "0"*64
    if mutation == "fake-quote": p.quotes = ["The company has guaranteed £70m revenue."]
    if mutation == "bad-index": p.fact_indexes = [99]
    if mutation == "number": p.text = p.text.replace("£0.7m", "£70m")
    if mutation == "bound": p.text = p.text.replace("more than ", "")
    if mutation == "expected": p.text = p.text.replace("expects", "secures")
    if mutation == "condition": p.text = "The board expects more than £0.7m annual revenue."
    if mutation == "no-support": p.fact_indexes = []
    if mutation == "external-link": p.text += " Read https://example.com."
    if mutation == "guaranteed": p.text = "The board expects guaranteed annual revenue of more than £0.7m, subject to development."
    with pytest.raises(FollowupQualityError): validate_answer(source, card, answer)


def test_absence_and_external_data_are_clearly_scoped_not_fabricated():
    source, card, _ = example()
    answer = FollowupAnswer(source_hash=source.source_hash, scope="needs_context", paragraphs=[{
        "text": "This paste does not provide a current share price or a profit margin for the contract. A valuation would need those missing inputs.",
        "kind": "limitation"}])
    assert validate_answer(source, card, answer)["scope"] == "needs_context"
    answer.paragraphs[0].text += " Its market value is £20m."
    with pytest.raises(FollowupQualityError): validate_answer(source, card, answer)


def test_proposed_dividend_is_not_paid():
    source, card, answer = example("spr")
    answer.paragraphs[0].text = "The company paid a 3.0p dividend versus 2.0p."
    with pytest.raises(FollowupQualityError): validate_answer(source, card, answer)


def test_cash_answer_preserves_date_and_subsequent_payment():
    source, card, answer = example("spr")
    answer.paragraphs = [answer.paragraphs[0].model_copy(update={"text":
        "Net bank cash was £1.2m at 31 May 2026, compared with £20.9m net bank debt. A subsequent £20.7m acquisition payment was made after year-end.",
        "fact_indexes": [2, 5]})]
    assert validate_answer(source, card, answer)["sources"]
    original = answer.model_copy(deep=True)
    answer.paragraphs[0].text = answer.paragraphs[0].text.split(" A subsequent")[0]
    with pytest.raises(FollowupQualityError, match="POST_PERIOD"): validate_answer(source, card, answer)
    answer = original
    answer.paragraphs[0].text = answer.paragraphs[0].text.replace(" at 31 May 2026", " today")
    with pytest.raises(FollowupQualityError, match="DATE"): validate_answer(source, card, answer)


def calculation_answer():
    source, card, _ = example("spr")
    quote = source.text.splitlines()[7]
    answer = FollowupAnswer(source_hash=source.source_hash, scope="answered", paragraphs=[{
        "text": "The proposed dividend is 50% higher, subject to shareholder approval.", "kind": "source", "quotes": [quote]}],
        calculations=[{"label": "Dividend increase", "value": "50%", "basis": "calculated", "assertion": "calculated",
            "note": "Percentage change from 2.0p to proposed 3.0p, subject to shareholder approval.",
            "evidence_quotes": [quote], "condition_quotes": ["subject to shareholder approval."],
            "calculation": {"operation": "percent-change", "left": {"value": "3.0p", "quote": quote},
                "right": {"value": "2.0p", "quote": quote}, "comparable_basis": "Annual dividend per ordinary share in both periods."}}])
    return source, card, answer


def test_source_backed_calculation_is_verified_and_visible():
    source, card, answer = calculation_answer()
    result = validate_answer(source, card, answer)
    assert result["calculations"][0]["note"] == answer.calculations[0].note


@pytest.mark.parametrize("mutation", ["wrong-result", "wrong-input", "unquoted", "hidden-input", "bound", "currency"])
def test_unsupported_followup_arithmetic_fails(mutation):
    source, card, answer = calculation_answer()
    fact = answer.calculations[0]
    if mutation == "wrong-result": fact.value = "70%"
    if mutation == "wrong-input": fact.calculation.right.value = "1.0p"
    if mutation == "unquoted": fact.calculation.left.quote = "Dividend is 4.0p."
    if mutation == "hidden-input": fact.note = "Calculated increase."
    if mutation == "bound": fact.calculation.left.value = "Up to 3.0p"
    if mutation == "currency": fact.calculation.left.value = "$3m"
    with pytest.raises(FollowupQualityError): validate_answer(source, card, answer)


@pytest.mark.parametrize("override", [{"question": "  "}, {"question": "x"*2001}, {"question": "hello\x00there"},
    {"turn_index": True}, {"turn_index": -1}, {"request_id": "short"}, {"analysis": {}}, {"history": []}, {"text": "replace source"}])
def test_question_boundary_is_text_only_and_strict(override):
    payload = question().model_dump(); payload.update(override)
    with pytest.raises(ValidationError): QuestionRequest.model_validate(payload)


@pytest.fixture
def stores():
    source, card, answer = example()
    calls = []
    now = [0.0]
    parents = PasteJobs(lambda _: card, clock=lambda: now[0], ttl=10)
    parent = parents.submit("owner-a", source)
    pid = parent["analysis_id"]
    wait(lambda: parents.get("owner-a", pid))
    def runner(s, c, h, q):
        calls.append((s.text, c, h, q))
        return validate_answer(s, c, answer)
    jobs = FollowupJobs(parents, runner, clock=lambda: now[0], owner_limit=20)
    yield source, card, parents, jobs, pid, calls, now
    jobs.close(); parents.close()


def test_followup_history_dedupe_and_model_context_are_server_owned(stores):
    source, card, parents, jobs, pid, calls, now = stores
    assert jobs.history("owner-a", pid)["turns"] == []
    assert calls == []
    first = jobs.submit("owner-a", pid, question())
    completed = wait(lambda: jobs.get("owner-a", pid, first["question_id"]))
    assert completed["status"] == "complete"
    assert jobs.submit("owner-a", pid, question())["question_id"] == first["question_id"]
    second = jobs.submit("owner-a", pid, question("What does that depend on?", 1))
    wait(lambda: jobs.get("owner-a", pid, second["question_id"]))
    assert len(calls) == 2 and calls[0][0] == source.text and calls[0][1]["headline"] == card["headline"]
    assert calls[0][2] == [] and calls[1][2][0]["question"] == question().question
    assert "source" not in parents.get("owner-a", pid)
    # No mutable reference can change server-held source or existing answers.
    s, c = parents.context("owner-a", pid); c["headline"] = "corrupted"
    assert parents.context("owner-a", pid)[1]["headline"] == card["headline"]
    completed["result"]["paragraphs"] = ["corrupted"]
    assert jobs.get("owner-a", pid, first["question_id"])["result"]["paragraphs"] != ["corrupted"]


def test_parent_and_question_cannot_be_read_by_another_owner(stores):
    source, card, parents, jobs, pid, calls, now = stores
    t = jobs.submit("owner-a", pid, question())
    for fn in (lambda: jobs.history("owner-b", pid), lambda: jobs.get("owner-b", pid, t["question_id"]),
               lambda: jobs.submit("owner-b", pid, question())):
        with pytest.raises(ConversationMissing): fn()
    assert parents.context("owner-b", pid) is None


def test_wrong_parent_never_reads_another_conversation(stores):
    source, card, parents, jobs, pid, calls, now = stores
    first = jobs.submit("owner-a", pid, question())
    other = parents.submit("owner-a", PasteRequest(text=source.text + " Extra text."))["analysis_id"]
    wait(lambda: parents.get("owner-a", other))
    with pytest.raises(ConversationMissing): jobs.get("owner-a", other, first["question_id"])


def test_expiry_removes_conversation_and_source(stores):
    source, card, parents, jobs, pid, calls, now = stores
    t = jobs.submit("owner-a", pid, question()); wait(lambda: jobs.get("owner-a", pid, t["question_id"]))
    now[0] = 11
    with pytest.raises(ConversationMissing): jobs.history("owner-a", pid)
    assert parents.context("owner-a", pid) is None
    assert jobs._conversations == {}


def test_stale_and_reused_request_ids_cannot_change_history(stores):
    source, card, parents, jobs, pid, calls, now = stores
    t = jobs.submit("owner-a", pid, question()); wait(lambda: jobs.get("owner-a", pid, t["question_id"]))
    with pytest.raises(ConversationConflict): jobs.submit("owner-a", pid, question("Changed contents", 0))
    with pytest.raises(ConversationConflict): jobs.submit("owner-a", pid, question("Another question", 0, "another-request-id"))
    assert len(calls) == 1


def test_eight_attempts_is_a_hard_per_announcement_cap(stores):
    source, card, parents, jobs, pid, calls, now = stores
    for i in range(8):
        t = jobs.submit("owner-a", pid, question(i=i)); wait(lambda: jobs.get("owner-a", pid, t["question_id"]))
    with pytest.raises(BusyError): jobs.submit("owner-a", pid, question(i=8))
    assert len(calls) == 8 and jobs.history("owner-a", pid)["remaining"] == 0
    assert jobs.submit("owner-a", pid, question())["turn_index"] == 0  # lost-response retry is free


def test_failure_is_sanitised_deduped_and_not_reused_as_evidence(stores, caplog):
    source, card, parents, jobs, pid, calls, now = stores
    def fail(*args): raise RuntimeError("SECRET token and private source")
    jobs.runner = fail
    first = jobs.submit("owner-a", pid, question()); result = wait(lambda: jobs.get("owner-a", pid, first["question_id"]))
    assert result["error_code"] == "ANSWER_UNAVAILABLE" and result["result"] is None
    assert "SECRET" not in str(result) + caplog.text
    jobs.submit("owner-a", pid, question())
    assert len(jobs.history("owner-a", pid)["turns"]) == 1


def test_no_concurrent_paid_questions_for_one_parent(stores):
    source, card, parents, jobs, pid, calls, now = stores
    started = threading.Event(); release = threading.Event()
    def slow(s, c, h, q): started.set(); release.wait(3); return {"source_hash": s.source_hash, "paragraphs": ["Test"]}
    jobs.runner = slow
    try:
        first = jobs.submit("owner-a", pid, question()); assert started.wait(1)
        assert jobs.submit("owner-a", pid, question())["question_id"] == first["question_id"]
        with pytest.raises(ConversationConflict): jobs.submit("owner-a", pid, question(i=1))
        now[0] = 11
    finally: release.set()
    jobs.close()
    assert jobs._conversations == {}


def test_owner_global_and_active_limits(stores):
    source, card, parents, jobs, pid, calls, now = stores
    jobs.owner_limit = 1
    t = jobs.submit("owner-a", pid, question()); wait(lambda: jobs.get("owner-a", pid, t["question_id"]))
    with pytest.raises(BusyError): jobs.submit("owner-a", pid, question(i=1))
    jobs.owner_limit = 20; jobs.hourly_limit = 1
    with pytest.raises(BusyError): jobs.submit("owner-a", pid, question(i=1))
    jobs.hourly_limit = 60; jobs._active = jobs.max_active
    with pytest.raises(BusyError): jobs.submit("owner-a", pid, question(i=1))
    jobs._active = 0


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("PASTE_ANALYSIS_ENABLED", "true"); monkeypatch.setenv("PASTE_CHAT_ENABLED", "true")
    source, card, answer = example()
    parents = PasteJobs(lambda _: card)
    calls = []
    def runner(s, c, h, q): calls.append(q); return validate_answer(s, c, answer)
    jobs = FollowupJobs(parents, runner)
    settings = SimpleNamespace(private_beta_mode=True, app_beta_password="test-only", openai_api_key="fake-test-key")
    app = Starlette(routes=[*create_paste_routes(lambda: parents, lambda: settings), *create_question_routes(lambda: jobs, lambda: settings)])
    client = TestClient(app); client.cookies.set("smallcaps_beta", _token(settings.app_beta_password))
    client.get("/api/v1/analyse")
    response = client.post("/api/v1/analyse", json={"text": source.text}, headers={"X-Smallcaps-Action": "analyse"})
    pid = response.json()["analysis_id"]
    wait(lambda: client.get(f"/api/v1/analyse/{pid}").json())
    yield client, app, settings, calls, f"/api/v1/analyse/{pid}/questions"
    client.close(); jobs.close(); parents.close()


def test_api_full_flow_and_cross_browser_privacy(api):
    client, app, settings, calls, url = api
    assert client.get(url).json()["turns"] == [] and calls == []
    t = client.post(url, json=question().model_dump(), headers={"X-Smallcaps-Action": "ask"}).json()
    result = wait(lambda: client.get(url + "/" + t["question_id"]).json())
    assert result["status"] == "complete" and len(calls) == 1
    response = client.get(url)
    assert response.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in response.headers
    with TestClient(app) as other:
        other.cookies.set("smallcaps_beta", _token(settings.app_beta_password))
        assert other.get(url).status_code == 404
        assert other.get(url + "/" + t["question_id"]).status_code == 404
        assert other.post(url, json=question().model_dump(), headers={"X-Smallcaps-Action": "ask"}).status_code == 404
    assert len(calls) == 1


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_api_beta_gate_never_exposes_anonymous_paid_endpoint(api, method):
    client, app, settings, calls, url = api
    client.cookies.clear()
    assert client.request(method, url).status_code == 401
    settings.private_beta_mode = False
    assert client.request(method, url).status_code == 503
    assert calls == []


@pytest.mark.parametrize("headers", [{}, {"X-Smallcaps-Action": "analyse"},
    {"X-Smallcaps-Action": "ask", "Origin": "https://attacker.invalid"}, {"X-Smallcaps-Action": "ask", "Origin": "null"}])
def test_qa_api_origin_checks(api, headers):
    client, app, settings, calls, url = api
    assert client.post(url, json=question().model_dump(), headers=headers).status_code == 403
    assert calls == []


def test_qa_api_invalid_input_limits_and_disable(api, monkeypatch):
    client, app, settings, calls, url = api
    h = {"X-Smallcaps-Action": "ask"}
    assert client.post(url, json={**question().model_dump(), "history": []}, headers=h).status_code == 422
    assert client.post(url, content="{}", headers=h).status_code == 415
    assert client.post(url, content="x"*16001, headers={**h, "Content-Type": "application/json"}).status_code == 413
    assert client.post(url, json={**question().model_dump(), "turn_index": 1}, headers=h).status_code == 409
    settings.openai_api_key = ""
    assert client.post(url, json=question().model_dump(), headers=h).status_code == 503
    monkeypatch.setenv("PASTE_CHAT_ENABLED", "false")
    assert client.get(url).status_code == 503
    assert calls == []


def test_sdk_one_request_no_retries_and_no_client_supplied_context(monkeypatch):
    source, card, answer = example()
    seen = {}
    class Client:
        def __init__(self, **kwargs): seen["client"] = kwargs; self.responses = self
        def __enter__(self): return self
        def __exit__(self, *args): seen["closed"] = True
        def parse(self, **kwargs): seen["request"] = kwargs; return SimpleNamespace(output_parsed=answer, usage=SimpleNamespace(input_tokens=100, output_tokens=50))
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
    from analyst import paste_chat
    monkeypatch.setattr(paste_chat.Settings, "from_env", lambda: SimpleNamespace(openai_api_key="test-only", openai_model="test-model"))
    result = answer_question(source, card, [], "Is this material?")
    assert seen["client"]["max_retries"] == 0 and seen["request"]["store"] is False
    assert seen["request"]["max_output_tokens"] == 3500 and "tools" not in seen["request"]
    assert "test-only" not in seen["request"]["input"] and seen["closed"]
    assert json.loads(seen["request"]["input"])["original_source"] == source.text
    assert result["telemetry"]["requests"] == 1


def test_strict_sdk_schema_conversion():
    pytest.importorskip("openai")
    from openai.lib._pydantic import to_strict_json_schema
    schema = to_strict_json_schema(FollowupAnswer)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_frontend_source_never_overwrites_card_or_stores_conversation():
    root = Path(__file__).resolve().parents[1]
    script = (root/"frontend/assets/analysis-questions.js").read_text()
    for bad in ("innerHTML", "localStorage", "sessionStorage", "eval(", "SmallcapsCard.render"):
        assert bad not in script
    html = (root/"frontend/analyse.html").read_text()
    assert 'id="questions"' in html and 'aria-labelledby="questions-title" hidden' in html
    assert "Ask about this announcement…" in html
    assert "request_id" in script and "turn_index" in script and "g !== generation" in script


def test_live_runner_preflight_never_makes_a_model_request(tmp_path, monkeypatch):
    from jobs.check_paste_conversation_live import run
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = tmp_path/"preflight.json"
    assert run(report) == 0
    data = json.loads(report.read_text())
    assert data["live_model"] is False and data["max_model_requests"] == 3
    assert data["launch_approved"] is False
    assert run(report, live=True, model="test-model") == 2
    assert json.loads(report.read_text())["status"] == "blocked-missing-model-or-credential"
