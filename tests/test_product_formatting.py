from product.formatting import (
    attention_count,
    attention_summary_label,
    compact_feed_fact_label,
    compact_feed_fact_value,
    concise_feed_view,
    fact_is_numeric,
    feed_comparator_text,
    feed_verdict,
    feed_view,
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


def test_attention_summary_has_correct_singular_and_plural_grammar() -> None:
    assert attention_summary_label(0) == "0 announcements need attention"
    assert attention_summary_label(1) == "1 announcement needs attention"
    assert attention_summary_label(8) == "8 announcements need attention"


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


def test_feed_compacts_known_long_evidence_labels_without_mutating_values() -> None:
    administration = {
        "label": "Notice of intention to appoint administrators",
        "value": "Filed",
    }
    assert compact_feed_fact_label(administration) == "Administration"
    assert compact_feed_fact_value(administration) == "Notice of intention filed"

    assert (
        compact_feed_fact_label(
            {
                "label": "Going concern funding position",
                "value": "Insufficient funds",
            }
        )
        == "Funding position"
    )
    assert (
        compact_feed_fact_label(
            {
                "label": "Potential shareholder recovery",
                "value": "No return expected",
            }
        )
        == "Shareholder recovery"
    )
    assert (
        compact_feed_fact_label(
            {"label": "Possible offer target", "value": "Whole company"}
        )
        == "Offer scope"
    )


def test_feed_hides_non_information_comparators_but_keeps_real_prior_values() -> None:
    assert (
        feed_comparator_text(
            {
                "value": "Filed",
                "previous_value": "No administration notice disclosed",
            }
        )
        == ""
    )
    assert (
        feed_comparator_text(
            {
                "value": "No return expected",
                "comparator": "Not disclosed in supplied prior context",
            }
        )
        == ""
    )
    assert (
        feed_comparator_text(
            {"value": "£18.2m", "previous_value": "£24.0m"}
        )
        == "£24.0m"
    )


def test_feed_verdict_promotes_supported_administration_outcome() -> None:
    item = {
        "headline": (
            "Trellus Health signals imminent administration amid going-concern shortfall"
        ),
        "takeaway": (
            "The company has insufficient funds to continue as a going concern and "
            "has filed a notice of intention to appoint administrators."
        ),
        "impact_rationale": "A thesis-changing liquidity failure.",
        "key_facts": [
            {
                "label": "Potential shareholder recovery",
                "value": "No returns to shareholders expected if any sale is concluded",
            }
        ],
    }
    assert feed_verdict(item) == "Administration imminent; no shareholder return expected"
    assert feed_view(item).startswith("Thesis broken.")


def test_feed_verdict_promotes_preliminary_takeover_without_inventing_terms() -> None:
    item = {
        "headline": (
            "Waterland takeover talks and possible divisional carve-out disclosed "
            "under Rule 2.4"
        ),
        "takeaway": "The company is in discussions about a possible offer.",
        "impact_rationale": "The process is preliminary and terms remain uncertain.",
        "key_facts": [
            {"label": "Potential bidder", "value": "Waterland Private Equity"}
        ],
    }
    assert feed_verdict(item) == "Formal takeover interest emerges; terms remain unknown"
    assert "no offer terms are disclosed yet" in feed_view(item)


def test_feed_verdict_does_not_overwrite_takeover_when_terms_are_known() -> None:
    headline = "Possible offer at 250p per share"
    item = {
        "headline": headline,
        "takeaway": "The bidder is considering a possible offer at 250p per share.",
        "key_facts": [],
    }
    assert feed_verdict(item) == headline


def test_preliminary_takeover_no_offer_price_is_treated_as_missing_terms() -> None:
    item = {
        "headline": "Rule 2.4 possible offer discussions",
        "takeaway": "No offer price has been disclosed.",
        "impact_rationale": "The situation remains preliminary.",
        "key_facts": [],
    }
    assert feed_verdict(item) == "Formal takeover interest emerges; terms remain unknown"


def test_completed_administrator_appointment_is_not_called_imminent() -> None:
    item = {
        "headline": "Administrators appointed",
        "takeaway": "Administrators have been appointed following the earlier notice.",
        "impact_rationale": "The company is now in administration.",
        "key_facts": [
            {
                "label": "Shareholder recovery",
                "value": "No return to shareholders expected",
            }
        ],
    }
    assert feed_verdict(item) == "Administration underway; no shareholder return expected"


def test_feed_view_is_capped_for_scanability() -> None:
    long = (
        "First sentence explains the main consequence. "
        "Second sentence explains what remains to prove. "
        "Third sentence belongs in the full note and should not be shown."
    )
    assert concise_feed_view(long) == (
        "First sentence explains the main consequence. "
        "Second sentence explains what remains to prove."
    )
