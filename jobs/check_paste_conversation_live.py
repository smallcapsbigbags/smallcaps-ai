"""Explicit opt-in live check of analysis followed by one source-scoped question.

Default preflight performs no model request. A live run is limited to one document,
up to two initial analysis requests and one answer request, with retries disabled.
It does not deploy code, alter Railway, or prove launch readiness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time


def run(output: Path, *, live: bool = False, model: str = "", case: str = "trt",
        source_file: Path | None = None, question: str = "What conditions apply to this announcement?") -> int:
    from product.paste import PasteRequest
    from product.paste_chat import QuestionRequest
    from jobs.paste_chat_cases import example
    source = PasteRequest(text=source_file.read_text(encoding="utf-8")) if source_file else example(case)[0]
    # Validate before any paid request; never use a CLI argument as an instruction template.
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
        from analyst.paste import analyse_paste
        from analyst.paste_chat import answer_question
        started = time.monotonic()
        try:
            report["live_model"] = True
            card = analyse_paste(source)
            report["analysis_telemetry"] = card.get("telemetry")
            report["card_review"] = {key: card[key] for key in ("headline", "summary", "what_changed", "what_matters")}
            answer = answer_question(source, card, [], q.question)
            report["answer_telemetry"] = answer.get("telemetry")
            report["answer_review"] = answer["paragraphs"]
            report["status"] = "bounded-checks-passed-human-review-required"
        except Exception as exc:
            report["status"] = "failed"; report["error_type"] = type(exc).__name__; code = 1
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    root = Path(__file__).resolve().parents[1]
    report["source_files"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root/"analyst/paste.py", root/"analyst/paste_chat.py", root/"product/paste_chat.py")}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
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
