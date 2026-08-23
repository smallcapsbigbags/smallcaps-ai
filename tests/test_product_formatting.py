from product.formatting import (
    attention_count,
    fact_is_numeric,
    format_price_change,
    impact_direction_label,
    impact_signal_label,
    public_rns_type,
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


def test_semantic_impact_labels_do_not_expose_colour_tokens() -> None:
    assert impact_signal_label("red", "critical") == "CRITICAL · ADVERSE"
    assert impact_signal_label("amber", "high") == "HIGH · MIXED"
    assert impact_signal_label("green", "medium") == "MEDIUM · FAVOURABLE"
    assert impact_signal_label("grey", "low") == "LOW · ROUTINE"
    assert impact_signal_label("grey", "high") == "HIGH · NEUTRAL"
    assert impact_direction_label("unknown", level="high") == "NEUTRAL"
    assert impact_signal_label("<script>", "<script>") == "LOW · ROUTINE"


def test_feed_hides_fallback_types_and_preserves_real_categories() -> None:
    assert public_rns_type("Other") == ""
    assert public_rns_type(" unclassified ") == ""
    assert public_rns_type("Results & trading") == "Results & trading"


def test_feed_numeric_typography_is_reserved_for_compact_data() -> None:
    assert fact_is_numeric({"value": "£18.2m", "value_numeric": 18.2})
    assert fact_is_numeric({"value": "18 Sep 2026 · 17:00"})
    assert not fact_is_numeric(
        {"value": "Insufficient to continue as a going concern"}
    )
    assert not fact_is_numeric(
        {"value": "No return expected from any successful asset sale"}
    )
