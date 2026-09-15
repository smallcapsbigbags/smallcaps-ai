"""Local served-browser acceptance of real auth/API/UI routes with stubbed AI only.

The isolated test server uses a test-only password and never constructs a model client.
No production flags or test backdoors are added to the application.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import socket
import threading
import time
from types import SimpleNamespace

import uvicorn
from playwright.sync_api import expect, sync_playwright
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from analyst.paste_chat import validate_answer
from api.frontend import create_frontend_routes
from api.paste import create_paste_routes
from api.paste_jobs import PasteJobs
from api.paste_questions import create_question_routes
from api.paste_conversations import FollowupJobs
from jobs.paste_chat_cases import example
from product.paste_chat import FollowupAnswer

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def fixture_server():
    env = {"PRIVATE_BETA_MODE": "true", "APP_BETA_PASSWORD": "local-qa-test-only",
           "PASTE_ANALYSIS_ENABLED": "true", "PASTE_CHAT_ENABLED": "true"}
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    cases = {name: example(name) for name in ("spr", "trt")}
    calls = {"analysis": 0, "questions": 0}
    def analysis(source):
        calls["analysis"] += 1
        for s, card, _ in cases.values():
            if source.source_hash == s.source_hash: return card
        raise ValueError("Only approved test excerpts are supported by this stub")
    def reply(source, card, history, question):
        calls["questions"] += 1
        if question.startswith("Slow"): time.sleep(.8)
        else: time.sleep(.12)
        if question.startswith("Fail"): raise RuntimeError("TEST-PRIVATE do not echo")
        if question.startswith("Literal"):
            answer = FollowupAnswer(source_hash=source.source_hash, scope="answered", paragraphs=[{
                "text": '<img src=x onerror="window.unsafeExecuted=true">', "kind": "general"}])
            return validate_answer(source, card, answer)
        name = "spr" if source.source_hash == cases["spr"][0].source_hash else "trt"
        return validate_answer(source, card, cases[name][2])
    parents = PasteJobs(analysis, owner_limit=20, hourly_limit=100)
    questions = FollowupJobs(parents, reply, owner_limit=20, hourly_limit=100)
    settings = SimpleNamespace(private_beta_mode=True, app_beta_password=env["APP_BETA_PASSWORD"], openai_api_key="stub-not-a-key")
    app = Starlette(routes=[*create_frontend_routes(),
        *create_paste_routes(lambda: parents, lambda: settings),
        *create_question_routes(lambda: questions, lambda: settings),
        Mount("/assets", app=StaticFiles(directory=ROOT/"frontend/assets"))])
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True); thread.start()
    for _ in range(300):
        if server.started: break
        time.sleep(.01)
    if not server.started: raise RuntimeError("Test server did not start")
    try: yield f"http://127.0.0.1:{port}", calls, cases
    finally:
        server.should_exit = True; thread.join(timeout=5)
        questions.close(); parents.close(); sock.close()
        for k, v in old.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v


def layout(page):
    errors = page.evaluate("""() => {
        const bad = [];
        if(document.documentElement.scrollWidth > innerWidth + 1) bad.push('page overflow');
        for (const el of document.querySelectorAll('.question-composer,.question-answer,.asked-question')) {
          if(el.scrollWidth > el.clientWidth + 1) bad.push('question overflow');
        }
        const ids = [...document.querySelectorAll('[id]')].map(el=>el.id);
        if(ids.length !== new Set(ids).size) bad.push('duplicate IDs');
        return bad;
    }""")
    assert errors == [], errors


def login(page, base):
    page.goto(base, wait_until="networkidle")
    page.locator("#access-code").fill("local-qa-test-only")
    page.locator('button[type="submit"]').click()
    expect(page.get_by_role("heading", name="See what matters.", exact=True)).to_be_visible()


def run(out: Path, executable: str | None = None):
    out.mkdir(parents=True, exist_ok=True)
    report = {"live_model": False, "method": "Actual frontend/auth/analysis/question API routes on an isolated localhost server; AI runners are hand-authored stubs.", "checks": []}
    with fixture_server() as (base, calls, cases), sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        for device, width, height in (("desktop",1440,1000),("tablet",768,1024),("mobile",390,844),("narrow",320,740)):
            context = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
            page = context.new_page()
            errors, requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda req: requests.append((req.method, req.url)))
            login(page, base)
            expect(page.locator("#questions")).to_be_hidden()
            assert not any("/api/" in url for _,url in requests)
            page.screenshot(path=out/f"landing-{device}.png", full_page=True)
            for name in ("trt", "spr"):
                source, card, _ = cases[name]
                page.locator("#rns-text").fill(source.text)
                expect(page.locator("#questions")).to_be_hidden()
                page.locator("#analyse-button").click()
                expect(page.locator("#result")).to_be_visible(timeout=15000)
                expect(page.locator("#question-text")).to_be_enabled()
                expect(page.locator("#questions")).to_be_visible()
                expect(page.locator("#question-button")).to_be_disabled()
                assert page.locator(".question-turn").count() == 0
                card_html = page.locator("#result").inner_html()
                page.locator("#result").screenshot(path=out/f"{name}-card-{device}.png")
                page.locator("#question-text").fill("Is this revenue guaranteed?" if name=="trt" else "Is the dividend increasing?")
                page.locator("#question-text").press("Control+Enter")
                expect(page.locator("#question-message")).to_have_text("Answer ready.", timeout=15000)
                expect(page.locator("#question-history")).to_contain_text("subject to")
                assert page.locator("#result").inner_html() == card_html
                assert page.locator("#question-text").input_value() == ""
                assert page.locator(".question-turn").count() == 1
                before = calls["questions"]
                page.locator(".answer-sources > summary").focus()
                page.locator(".answer-sources > summary").press("Enter")
                expect(page.locator(".answer-sources blockquote").first).to_be_visible()
                assert page.locator(".answer-sources > summary").bounding_box()["height"] >= 44
                page.locator(".answer-sources > summary").press("Enter")
                assert calls["questions"] == before
                layout(page)
                page.locator("#questions").screenshot(path=out/f"{name}-conversation-{device}.png")
                if name == "trt": page.screenshot(path=out/f"journey-{device}.png", full_page=True)
                page.locator("#question-text").fill("And what does that mean?")
                page.locator("#question-button").click()
                expect(page.locator("#question-message")).to_have_text("Answer ready.", timeout=15000)
                assert page.locator(".question-turn").count() == 2
                assert not errors, errors
                report["checks"].append({"case":name,"width":width,"passed":True,"card_unchanged":True})
            # Oversized questions are kept for editing, never silently truncated.
            page.locator("#question-text").fill("x"*2001)
            expect(page.locator("#question-button")).to_be_disabled()
            assert len(page.locator("#question-text").input_value()) == 2001
            # A server-completed POST whose browser response is lost must not spend again.
            lost = {"done": False}
            pattern = re.compile(r"/questions$")
            def drop_once(route):
                if route.request.method == "POST" and not lost["done"]:
                    lost["done"] = True
                    route.fetch(); route.abort("failed")
                else: route.continue_()
            page.route(pattern, drop_once)
            page.locator("#question-text").fill("Can you clarify that?")
            before = calls["questions"]
            page.locator("#question-button").click()
            expect(page.locator("#question-message")).to_contain_text("Connection interrupted", timeout=15000)
            expect(page.locator("#question-button-label")).to_have_text("Check answer")
            page.wait_for_timeout(250)
            assert calls["questions"] == before + 1
            page.locator("#question-button").click()
            expect(page.locator("#question-message")).to_have_text("Answer ready.", timeout=15000)
            assert calls["questions"] == before + 1
            page.unroute(pattern, drop_once)
            # Server failure keeps the draft and never removes the card.
            page.locator("#question-text").fill("Fail this test question")
            page.locator("#question-button").click()
            expect(page.locator("#question-message")).to_contain_text("wasn’t completed", timeout=15000)
            assert page.locator("#question-text").input_value() == "Fail this test question"
            expect(page.locator("#result")).to_be_visible()
            # Untrusted question/answer text must remain literal.
            page.locator("#question-text").fill('Literal <img src=x onerror="window.unsafeExecuted=true">')
            page.locator("#question-button").click()
            expect(page.locator("#question-message")).to_have_text("Answer ready.", timeout=15000)
            assert page.locator("#questions img").count() == 0
            assert page.evaluate("window.unsafeExecuted === undefined")
            # Start an old question, then switch documents. Its answer cannot leak into the new one.
            page.locator("#question-text").fill("Slow answer while I change announcements")
            page.locator("#question-button").click()
            expect(page.locator("#question-text")).to_be_disabled()
            expect(page.locator(".asked-question").last).to_contain_text("Slow answer")
            page.locator("#rns-text").fill(cases["trt"][0].text)
            expect(page.locator("#questions")).to_be_hidden()
            page.locator("#analyse-button").click()
            expect(page.locator("#result-headline")).to_have_text(cases["trt"][1]["headline"], timeout=15000)
            expect(page.locator("#question-text")).to_be_enabled()
            page.wait_for_timeout(1600)
            expect(page.locator("#question-history")).not_to_contain_text("Slow answer")
            # Existing TRT conversation is recovered from the server, without a model call.
            assert page.locator(".question-turn").count() == 2
            layout(page)
            assert not errors, errors
            if device == "desktop":
                qurl = next(url for _,url in reversed(requests) if url.endswith("/questions"))
                other = browser.new_context(); other_page = other.new_page(); login(other_page, base)
                assert other.request.get(qurl).status == 404
                other.close()
                # Logout removes access, yet the draft stays available for copying.
                page.request.post(base+"/logout")
                page.locator("#question-text").fill("Is this still available?")
                page.locator("#question-button").click()
                expect(page.locator("#question-sign-in")).to_be_visible()
                assert page.locator("#question-text").input_value() == "Is this still available?"
            report["checks"].append({"width":width,"lost_post_deduplicated":True,"source_switch_isolated":True,
                "literal_markup":True,"oversized_input_preserved":True,"passed":True})
            context.close()
        browser.close()
    report["passed"] = True
    (out/"conversation-checks.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("/tmp/paste-conversation-checks"))
    parser.add_argument("--chromium-executable",default=None)
    args=parser.parse_args(); run(args.output,args.chromium_executable)
