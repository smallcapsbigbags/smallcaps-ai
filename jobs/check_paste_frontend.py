"""Browser checks of real served assets, with fixture analysis responses only."""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

SOURCE = """RNS Number : 7173U
Transense Technologies PLC
15 September 2026
Contract award with Continental to develop next-generation tyre management tool
A funded six-month development and supply programme for a bespoke TLGX device.
Production is expected from Q2 2027 following successful development.
The board expects more than £0.7m annual revenue from future deployments.
"""
CARD = {
    "identity": {"company": "Transense Technologies PLC", "ticker": None, "publication_date": "2026-09-15"},
    "headline": "Continental funds tyre-tool development",
    "summary": "A funded six-month programme will develop a bespoke TLGX device. Production is expected from Q2 2027 following successful development.",
    "facts": [
        {"label": "Development", "value": "6 months", "basis": "reported", "metric": "development", "note": "Funded programme"},
        {"label": "Expected production", "value": "From Q2 2027", "basis": "reported", "metric": "production", "note": "Following successful development"},
        {"label": "Expected annual revenue", "value": ">£0.7m", "basis": "reported", "metric": "annual revenue", "period": "Future deployments", "note": "Subject to development and deployment"},
    ],
    "what_changed": "The existing Continental relationship has expanded into a funded development and supply programme.",
    "what_matters": ["Future revenue depends on successful development and subsequent deployment."],
    "direction": "green", "materiality": 2,
    "materiality_rationale": "A funded programme adds a conditional future revenue opportunity.",
}


def layout(page) -> None:
    dimensions = page.evaluate("""() => ({width: innerWidth,
        html: document.documentElement.scrollWidth, body: document.body.scrollWidth})""")
    assert max(dimensions["html"], dimensions["body"]) <= dimensions["width"] + 1, dimensions


def run(base: str, out: Path) -> None:
    # This helper must never be aimed at a deployed paid endpoint.
    if urlparse(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Use a local test server; analysis responses are fixtures.")
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, width, height in (("desktop", 1440, 1000), ("mobile", 390, 844)):
            context = browser.new_context(viewport={"width": width, "height": height}, is_mobile=name == "mobile")
            page = context.new_page()
            failures, requests_seen = [], []
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.on("request", lambda request: requests_seen.append(request.url))
            state = {"posts": 0, "polls": 0, "fail": False, "card": copy.deepcopy(CARD)}

            def fixture(route):
                request = route.request
                path = urlparse(request.url).path
                if request.method == "POST":
                    state["posts"] += 1
                    state["polls"] = 0
                    assert request.headers.get("x-smallcaps-action") == "analyse"
                    assert isinstance(request.post_data_json["text"], str)
                    if state["fail"]:
                        route.fulfill(status=503, json={"error": {"code": "ANALYSIS_UNAVAILABLE", "message": "Analysis is temporarily unavailable. Your text is still here."}})
                        return
                    payload = {"analysis_id": "fixture-job", "status": "processing"}
                elif path == "/api/v1/analyse":
                    payload = {"ready": True}
                else:
                    state["polls"] += 1
                    payload = {"analysis_id": "fixture-job", "status": "processing" if state["polls"] == 1 else "complete", "result": state["card"]}
                route.fulfill(status=200, json=payload)

            # A suffix glob attached to 'analyse' does not reliably cross '/'.
            # Explicitly intercept both handshake/submission and every status poll.
            page.route(re.compile(r"/api/v1/analyse(?:/[^?]*)?(?:\?.*)?$"), fixture)
            page.goto(base, wait_until="networkidle")
            expect(page.get_by_role("heading", name="See what matters.", exact=True)).to_be_visible()
            expect(page.locator("#analyse-button")).to_be_disabled()
            assert not any("/api/" in url for url in requests_seen), requests_seen
            assert page.locator("nav").count() == 0
            layout(page)
            page.screenshot(path=out / f"landing-{name}.png", full_page=True)
            page.locator("#rns-text").fill(SOURCE)
            expect(page.locator("#analyse-button")).to_be_enabled()
            page.screenshot(path=out / f"input-{name}.png", full_page=True)
            page.locator("#rns-text").press("Control+Enter")
            expect(page.locator("#rns-text")).to_be_disabled()
            page.screenshot(path=out / f"loading-{name}.png", full_page=True)
            try:
                expect(page.locator("#result")).to_be_visible(timeout=20000)
            except AssertionError:
                page.screenshot(path=out / f"failure-{name}.png", full_page=True)
                print(json.dumps({"viewport": name, "message": page.locator("#form-message").inner_text(), "posts": state["posts"], "polls": state["polls"], "requests": requests_seen, "page_errors": failures}))
                raise
            expect(page.locator("#result")).to_contain_text("Future revenue depends on successful development")
            expect(page.locator("#result")).to_contain_text("Not independently verified")
            assert page.locator(".metric-icon").count() == 3
            assert page.locator(".ticker").count() == 0
            assert state["posts"] == 1
            assert state["polls"] == 2
            layout(page)
            page.screenshot(path=out / f"result-{name}.png", full_page=True)

            # Model output must be rendered literally, never treated as HTML.
            state["card"]["summary"] = '<img src=x onerror="window.unsafeExecuted=true">'
            page.locator("#rns-text").fill(SOURCE + " Additional context.")
            page.locator("#analyse-button").click()
            expect(page.locator("#result")).to_be_visible(timeout=20000)
            assert page.locator("#result img").count() == 0
            assert page.evaluate("window.unsafeExecuted === undefined")
            expect(page.locator("#result")).to_contain_text("<img src=x")

            page.locator("#rns-text").fill("x" * 120001)
            assert len(page.locator("#rns-text").input_value()) == 120001
            expect(page.locator("#analyse-button")).to_be_disabled()
            expect(page.locator("#result")).to_be_hidden()

            state["fail"] = True
            before = state["posts"]
            page.locator("#rns-text").fill(SOURCE)
            page.locator("#analyse-button").click()
            expect(page.locator("#form-message")).to_contain_text("temporarily unavailable")
            expect(page.locator("#rns-text")).to_be_enabled()
            expect(page.locator("#result")).to_be_hidden()
            assert page.locator("#rns-text").input_value() == SOURCE
            page.wait_for_timeout(300)
            assert state["posts"] == before + 1
            assert failures == [], failures
            results.append({"viewport": name, "passed": True, "overflow": False, "literal_html": True, "qualifiers_visible": True, "no_automatic_paid_retry": True})
            context.close()
        browser.close()
    report = {"method": "Real local HTTP server and production assets; analysis API responses intercepted with fixtures", "live_model": False, "results": results}
    (out / "browser-checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8501")
    parser.add_argument("--output", type=Path, default=Path("/tmp/paste-mvp-browser"))
    args = parser.parse_args()
    run(args.base, args.output)
