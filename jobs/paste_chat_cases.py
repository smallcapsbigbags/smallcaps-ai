"""Hand-authored source-scoped QA controls. Never used by production generation."""
from __future__ import annotations

from analyst.paste_evidence import EvidenceAnalystNote
from analyst.paste_integrity import assess_paste_integrity
from jobs.paste_test_cases import load_integrity_cases
from product.paste import PasteRequest, project_paste_result
from product.paste_chat import FollowupAnswer


def example(name: str = "trt") -> tuple[PasteRequest, dict, FollowupAnswer]:
    case = next(c for c in load_integrity_cases() if c["id"] == name)
    source = PasteRequest(text=case["source"])
    note = EvidenceAnalystNote(source_id=source.source_id, **case["note"])
    card = project_paste_result(source, note)
    card["integrity"] = assess_paste_integrity(source.text, note).record()
    card["versions"] = {"editorial": "paste-editorial-2b"}
    assert card["integrity"]["status"] == "passed"
    text = ("The board expects more than £0.7m annual revenue from future deployments, "
            "subject to successful development and subsequent deployment.") if name == "trt" else (
            "The board proposes a 3.0p dividend versus 2.0p, subject to shareholder approval.")
    answer = FollowupAnswer(source_hash=source.source_hash, scope="answered", paragraphs=[{
        "text": text, "kind": "source", "quotes": [], "fact_indexes": [2 if name == "trt" else 3]}, {
        "text": ("Annual deployment revenue is not the same as a guaranteed recurring order.") if name == "trt" else (
            "The higher dividend is a proposal, not confirmation that it has been paid."),
        "kind": "general", "quotes": [], "fact_indexes": []}])
    return source, card, answer
