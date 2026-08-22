from pathlib import Path

from analyst.version import ANALYSIS_VERSION, DEFAULT_PROMPT_VERSION


def test_analyst_engine_v2_prompt_contains_locked_method_and_event_rules():
    prompt = Path("prompts/ANALYST_ENGINE_V2.md").read_text(encoding="utf-8")
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
    prompt = Path("prompts/PLAIN_ENGLISH_ANALYST_V1.md").read_text(encoding="utf-8")
    for token in (
        "Sceptical, not cynical",
        "Commercially minded",
        "Management says → Facts show → Smallcaps.ai explains what it means",
        "Reported, calculated and inferred",
        'basis="calculated"',
        "concept_explanations",
        "Rule 9",
        "normal investor",
    ):
        assert token in prompt


def test_gold_standard_prompt_locks_human_grade_decision_rules():
    prompt = Path("prompts/GOLD_STANDARD_ANALYST_V1.md").read_text(encoding="utf-8")
    for token in (
        "Pick the economically meaningful KPI",
        "Run the contradiction check",
        "Do the obvious maths",
        "Ask whether the change is repeatable",
        "Make the investment-case change explicit",
        "Loss-making life sciences",
        "Small beats after fresh guidance",
        "Buybacks, Rule 9 and control",
        "Market reaction remains separate",
    ):
        assert token in prompt


def test_benchmark_override_prompt_locks_repeated_failure_fixes():
    prompt = Path("prompts/GOLD_STANDARD_OVERRIDES_V1.md").read_text(encoding="utf-8")
    for token in (
        "Revenue growth must never hide deteriorating economics",
        "Loss-making life sciences: cash and funding first",
        "Earnings downgrades are adverse",
        "New information outranks known risk",
        "Signed contracts: distinguish modest value from no value",
        "Acquisition denominator matching is mandatory",
        "Buyback / Rule 9 calculations stay simple",
        "Conditional wind-down progress is not automatically high Impact",
        "Comparator metadata hygiene",
    ):
        assert token in prompt


def test_final_consistency_review_locks_evidence_and_impact_checks():
    prompt = Path("prompts/ANALYST_CONSISTENCY_REVIEW_V1.md").read_text(encoding="utf-8")
    for token in (
        "same supplied announcement evidence",
        "coverage_status` MUST be `building",
        "Main economic change",
        "Impact direction and significance",
        "Comparator integrity",
        "Useful maths",
        "Investment-case change",
        "no unsupported comparator",
    ):
        assert token in prompt

    assert ANALYSIS_VERSION == "aim-intelligence-analyst-2.2"
    assert DEFAULT_PROMPT_VERSION == "analyst-engine-2.2-gold-standard"
