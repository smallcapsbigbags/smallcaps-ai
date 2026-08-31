from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    GuidanceEvent,
    ImpactDriver,
    KeyFact,
    WhatChanged,
)
from product.news_contract import SupportedChange
from product.news_projection import project_company_news


def announcement() -> AnnouncementInput:
    return AnnouncementInput(
        source_id="spr-current",
        ticker="SPR.L",
        company="Springfield Properties",
        published_at=datetime(2026, 8, 31, 7, 0, tzinfo=timezone.utc),
        title="Land Sale and Deferred Consideration",
        text=(
            "The company has completed a £12.0m land sale covering 170 plots. "
            "Net debt is £18.2m versus £24.0m previously. Guidance is maintained."
        ),
        source_url="https://example.invalid/spr-current",
        source_urls=["https://example.invalid/spr-current"],
        rns_type="Disposal",
    )


def note(**updates: object) -> AnalystNote:
    values: dict[str, object] = {
        "source_id": "spr-current",
        "rns_type": "Disposal",
        "impact_colour": "green",
        "impact_score": 4,
        "impact_level": "high",
        "impact_rationale": "Cash proceeds and lower net debt improve the balance sheet.",
        "impact_drivers": [
            ImpactDriver(
                dimension="balance-sheet",
                direction="favourable",
                significance=4,
                rationale="Net debt reduced to £18.2m from £24.0m.",
            )
        ],
        "headline": "£12m land sale brings in cash",
        "takeaway": (
            "£12m land sale completed. Net debt now £18.2m versus £24.0m previously. "
            "Guidance unchanged."
        ),
        "key_facts": [
            KeyFact(
                label="Cash consideration",
                value="£12.0m",
                basis="reported",
                metric="cash consideration",
                currency="GBP",
                value_numeric=12.0,
            ),
            KeyFact(
                label="Plots",
                value="170",
                basis="reported",
                metric="plots",
                value_numeric=170,
            ),
            KeyFact(
                label="Net debt",
                value="£18.2m",
                basis="reported",
                metric="net debt",
                currency="GBP",
                value_numeric=18.2,
                previous_value="£24.0m",
                comparator="Prior disclosure £24.0m",
                comparator_type="prior-disclosure",
                comparator_source_id="spr-prior",
            ),
            KeyFact(
                label="Disposal margin",
                value="Not disclosed",
                basis="not-disclosed",
            ),
        ],
        "what_changed": WhatChanged(
            before="Net debt was £24.0m.",
            today="Net debt is £18.2m and the £12.0m land sale has completed.",
            read_through="Lower debt reduces balance-sheet risk.",
            coverage_status="established",
        ),
        "analyst_view": (
            "Good update. Cash is in and net debt is lower. Guidance is unchanged."
        ),
        "guidance_events": [
            GuidanceEvent(
                metric="FY guidance",
                value="In line",
                status="maintained",
                previous_value="In line",
                previous_source_id="spr-prior",
            )
        ],
        "watch_items": ["Next reported net debt.", "Cash conversion at results."],
        "disclosure_assessment": DisclosureAssessment(status="complete"),
        "source_references": ["https://example.invalid/spr-current"],
        "confidence": 0.93,
    }
    values.update(updates)
    return AnalystNote(**values)


def test_facts_contract_is_loaded_last_into_initial_and_review_prompts() -> None:
    source = Path("analyst/analyzer.py").read_text(encoding="utf-8")
    assert "FACTS_NO_FLUFF_OUTPUT_CONTRACT_V1.md" in source
    assert "facts_prompt_path" in source
    assert source.count("facts_prompt,") >= 2
    assert "Treat takeaway as the public Company News take" in source
    assert "unsupported inference or speculation must be removed" in source


def test_prompt_maps_rich_analyst_note_to_compact_public_fields() -> None:
    contract = Path("prompts/FACTS_NO_FLUFF_OUTPUT_CONTRACT_V1.md").read_text(
        encoding="utf-8"
    )
    for token in (
        "Current AnalystNote field mapping",
        "public `take` ← `takeaway`",
        "public `material_facts` ← **all decision-useful** `key_facts`",
        "public `baseline_status` ← `what_changed.coverage_status`",
        "Unsupported INFERRED or SPECULATIVE claims are prohibited",
    ):
        assert token in contract


def test_projection_preserves_all_material_facts_and_supported_changes() -> None:
    item = project_company_news(announcement(), note())

    assert item.ticker == "SPR"
    assert item.direction == "positive"
    assert item.materiality == 4
    assert item.key_news is True
    assert item.take.startswith("£12m land sale completed")
    assert len(item.material_facts) == 4
    assert item.material_facts[-1].value == "Not disclosed"
    assert item.material_facts[-1].basis == "not-disclosed"

    changes = {change.label: change for change in item.changes}
    assert changes["Net debt"].before == "£24.0m"
    assert changes["Net debt"].today == "£18.2m"
    assert changes["Net debt"].direction == "down"
    assert changes["Net debt"].comparator_source_id == "spr-prior"
    assert changes["FY guidance"].direction == "flat"
    assert changes["FY guidance"].before == "In line"


def test_building_coverage_establishes_baseline_without_fake_change() -> None:
    current = note(
        key_facts=[
            KeyFact(
                label="Net debt",
                value="£18.2m",
                basis="reported",
                metric="net debt",
                value_numeric=18.2,
            )
        ],
        guidance_events=[],
        what_changed=WhatChanged(
            before="Coverage is building.",
            today="Net debt is £18.2m.",
            read_through="Current balance-sheet baseline established.",
            coverage_status="building",
        ),
    )
    item = project_company_news(announcement(), current)

    assert item.baseline_status == "building"
    assert item.material_facts[0].value == "£18.2m"
    assert item.changes == []


def test_explicit_guidance_transition_is_allowed_without_stored_prior_value() -> None:
    current = note(
        key_facts=[],
        guidance_events=[
            GuidanceEvent(metric="FY guidance", status="maintained", value="In line")
        ],
        what_changed=WhatChanged(
            before="Coverage is building.",
            today="FY guidance remains in line.",
            read_through="No earnings guidance change disclosed.",
            coverage_status="building",
        ),
    )
    item = project_company_news(announcement(), current)

    assert len(item.changes) == 1
    assert item.changes[0].basis == "explicit-transition"
    assert item.changes[0].direction == "flat"


def test_compared_change_cannot_exist_without_before_value() -> None:
    with pytest.raises(ValidationError, match="supported before value"):
        SupportedChange(
            label="Net debt",
            direction="down",
            today="£18.2m",
            basis="compared",
            source_id="spr-current",
        )


def test_legacy_long_take_uses_shorter_existing_analyst_view_without_new_ai_call() -> None:
    long_take = " ".join(["word"] * 60)
    current = note(takeaway=long_take, analyst_view="Cash in. Net debt lower. Guidance unchanged.")
    item = project_company_news(announcement(), current)

    assert item.take == "Cash in. Net debt lower. Guidance unchanged."
    assert len(item.take.split()) <= 45


def test_projection_rejects_source_mismatch() -> None:
    with pytest.raises(ValueError, match="source_id must match"):
        project_company_news(announcement(), note(source_id="wrong-source"))
