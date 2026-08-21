from product.formatting import (
    attention_count,
    format_price_change,
    select_feed_facts,
)


def test_price_formatting_and_attention_count() -> None:
    assert format_price_change(None) == "—"
    assert format_price_change({"daily_change_pct": 5.04}) == "+5.0%"
    assert format_price_change({"daily_change_pct": -3.26}) == "-3.3%"
    assert attention_count(
        [
            {"impact_score": 5},
            {"impact_score": 3},
            {"impact_score": 2},
        ]
    ) == 2


def test_feed_facts_exclude_missing_and_source_warning_rows() -> None:
    facts = [
        {"label": "Undisclosed", "value": "Not disclosed", "basis": "not-disclosed"},
        {"label": "Warning", "value": "Conflict", "basis": "source-warning"},
        {"label": "Net debt", "value": "£18.2m", "basis": "reported"},
    ]
    assert select_feed_facts(facts) == [facts[2]]
