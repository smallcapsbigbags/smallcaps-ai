from pathlib import Path

from analyst.version import ANALYSIS_VERSION, DEFAULT_PROMPT_VERSION


def test_analyst_engine_v2_prompt_contains_locked_method_and_event_rules():
    prompt = Path("prompts/ANALYST_ENGINE_V2.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "EXTRACT → VERIFY → RANK → COMPARE → CHALLENGE → INTERPRET → SCORE → WRITE",
        "Results and trading updates",
        "Contracts and orders",
        "Fundraisings, placings and convertibles",
        "Acquisitions and disposals",
        "Takeovers and schemes",
        "Director dealings, holdings and ownership",
        "Disclosure assessment",
        "versus what?",
    ):
        assert token in prompt

    assert "Buy, Sell or Hold recommendations" in prompt


def test_phase2_plain_english_prompt_contains_locked_character_and_transparency_rules():
    prompt = Path("prompts/PLAIN_ENGLISH_ANALYST_V1.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "Sceptical, not cynical",
        "Commercially minded",
        "Management says → Facts show → Smallcaps.ai explains what it means",
        "Reported, calculated and inferred",
        "Smallcaps.ai calculation",
        "concept_explanations",
        "Rule 9",
        "normal investor",
    ):
        assert token in prompt

    assert ANALYSIS_VERSION == "aim-intelligence-analyst-2.1"
    assert DEFAULT_PROMPT_VERSION == "analyst-engine-2.1-plain-english"
