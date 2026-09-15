"""Opt-in live analysis and follow-up check. No automatic retries or gate bypass.

Preflight makes no model request. Live mode allows at most two analysis requests
and one answer. Diagnostic candidate text is confined to repository fixtures.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import time
from unittest.mock import patch


def run(output: Path, *, live: bool = False, model: str = "", case: str = "trt",
        source_file: Path | None = None, question: str = "What conditions apply to this announcement?") -> int:
    from product.paste import PasteRequest
    from product.paste_chat import QuestionRequest
    from jobs.paste_chat_cases import example
    source = PasteRequest(text=source_file.read_text(encoding="utf-8")) if source_file else example(case)[0]
    q = QuestionRequest(question=question, request_id="explicit-live-check", turn_index=0)
    report = {"mode": "live" if live else "preflight", "live_model": False,
        "status": "preflight-only-no-model-request", "source_hash": source.source_hash,
        "source_characters": len(source.text), "source_kind": "operator-supplied-text" if source_file else "fixture-excerpt",
        "model": model or None, "api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
        "max_model_requests": 3, "analysis_output_token_limit": 8000, "answer_output_token_limit": 3500,
        "automatic_retries": 0, "human_review_required": True, "launch_approved": False,
        "limitations": ["Source matching does not authenticate the paste or prove semantic correctness.",
                        "Request/token limits are not a provider-side monetary spending cap.",
                        "Human review of accuracy, omissions, natural writing and timing is required."]}
    code = 0
    if live and (not model.strip() or not report["api_key_configured"]):
        report["status"] = "blocked-missing-model-or-credential"; code = 2
    elif live:
        os.environ["OPENAI_MODEL"] = model
        os.environ["OPENAI_MAX_OUTPUT_TOKENS"] = "8000"
        import analyst.paste as adapter
        from analyst.paste_chat import answer_question
        from pydantic import ValidationError
        started = time.monotonic()
        try:
            report["live_model"] = True
            with ExitStack() as instrumentation:
                # All observers call the original implementation exactly once and
                # return it unchanged. They never correct output or suppress errors.
                if source_file is None:
                    original_integrity = adapter.assess_paste_integrity
                    original_quality = adapter.merge_monitoring_quality
                    original_engine = adapter.OpenAIAnalystEngine
                    class ObservedEngine(original_engine):
                        def analyse(self, *args, **kwargs):
                            try:
                                return super().analyse(*args, **kwargs)
                            finally:
                                report["analysis_telemetry"] = {"requests": self.request_calls, "usage": self.usage_records}
                    def observed_integrity(text, note):
                        checked = original_integrity(text, note)
                        report["integrity_findings"] = [{"code": f.code, "field": f.field} for f in checked.findings]
                        report["fixture_candidate"] = note.model_dump(mode="json")
                        return checked
                    def observed_quality(*args, **kwargs):
                        checked = original_quality(*args, **kwargs)
                        report["quality_status"] = checked.status
                        report["quality_flags"] = [{"code": f.code, "severity": f.severity} for f in checked.flags]
                        return checked
                    instrumentation.enter_context(patch.object(adapter, "OpenAIAnalystEngine", ObservedEngine))
                    instrumentation.enter_context(patch.object(adapter, "assess_paste_integrity", observed_integrity))
                    instrumentation.enter_context(patch.object(adapter, "merge_monitoring_quality", observed_quality))
                card = adapter.analyse_paste(source)
            report.pop("fixture_candidate", None)
            report["analysis_telemetry"] = card.get("telemetry")
            report["card_review"] = {key: card[key] for key in ("headline", "summary", "what_changed", "what_matters")}
            answer = answer_question(source, card, [], q.question)
            report["answer_telemetry"] = answer.get("telemetry")
            report["answer_review"] = answer["paragraphs"]
            report["status"] = "bounded-checks-passed-human-review-required"
        except Exception as exc:
            report["status"] = "failed"; report["error_type"] = type(exc).__name__; code = 1
            if source_file is None and isinstance(exc, ValidationError):
                report["validation_errors"] = [{"type": e["type"], "location": list(e["loc"]), "message": e["msg"]}
                    for e in exc.errors(include_input=False, include_url=False, include_context=False)]
            # Never log provider exception messages, headers, keys or response bodies.
            status = getattr(exc, "status_code", None)
            if isinstance(status, int) and 400 <= status <= 599:
                report["provider_status"] = status
            provider_code = getattr(exc, "code", None)
            if provider_code in {"insufficient_quota", "rate_limit_exceeded", "organization_spend_limit_exceeded",
                                 "model_not_found", "invalid_api_key", "invalid_json_schema"}:
                report["provider_code"] = provider_code
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    root = Path(__file__).resolve().parents[1]
    report["source_files"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root/"analyst/paste.py", root/"analyst/paste_chat.py", root/"product/paste_chat.py")}
    output.parent.mkdir(parents=True, exist_ok=True)
    # One JSON record avoids dropping the decisive diagnostics at Railway's
    # per-second line-rate limit. Do not log copies of intermediate model notes.
    output.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":"))+"\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "live_model": report["live_model"], "report": str(output)}))
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/tmp/paste-conversation-live.json"))
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--case", choices=["spr", "trt"], default="trt")
    parser.add_argument("--source", type=Path, help="Optional complete plain-text RNS for operator-run acceptance")
    parser.add_argument("--question", default="What conditions apply to this announcement?")
    args = parser.parse_args()
    raise SystemExit(run(args.output, live=args.live, model=args.model, case=args.case,
                         source_file=args.source, question=args.question))
