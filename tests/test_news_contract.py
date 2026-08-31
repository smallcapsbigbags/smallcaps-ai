from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from product.news_contract import (
    PRODUCT_NAME,
    PRODUCT_TAGLINE,
    CompanyNewsItem,
    direction_from_colour,
    is_key_news,
    materiality_circles,
)


def test_positioning_is_locked() -> None:
    assert PRODUCT_NAME == "smallcaps.ai"
    assert PRODUCT_TAGLINE == "AIM company news. Facts. No fluff."


def test_direction_is_independent_from_materiality() -> None:
    assert direction_from_colour("green") == "positive"
    assert direction_from_colour("amber") == "mixed"
    assert direction_from_colour("red") == "negative"
    assert direction_from_colour("grey") == "neutral"


def test_materiality_uses_five_neutral_circles() -> None:
    assert materiality_circles(1) == "●○○○○"
    assert materiality_circles(3) == "●●●○○"
    assert materiality_circles(5) == "●●●●●"


@pytest.mark.parametrize("score,expected", [(1, False), (2, False), (3, True), (4, True), (5, True)])
def test_key_news_surfaces_only_materiality_three_plus(score: int, expected: bool) -> None:
    assert is_key_news(score) is expected


def test_compact_news_item_exposes_locked_public_semantics() -> None:
    item = CompanyNewsItem(
        source_id="spr-2026-08-31",
        ticker="spr.l",
        company="Springfield Properties",
        published_at=datetime(2026, 8, 31, 7, 0, tzinfo=timezone.utc),
        news_type="Disposal",
        direction="positive",
        materiality=4,
        headline="£12m land sale brings in cash",
        take="£12m sale. More cash in. Guidance unchanged.",
        baseline_status="building",
    )

    assert item.ticker == "SPR"
    assert item.key_news is True
    assert item.materiality_display == "●●●●○"
    assert item.direction_label == "Positive"


def test_take_is_hard_capped_at_45_words() -> None:
    too_long = " ".join(["word"] * 46)
    with pytest.raises(ValidationError, match="45 words or fewer"):
        CompanyNewsItem(
            source_id="abc-1",
            ticker="ABC",
            company="ABC plc",
            published_at=datetime(2026, 8, 31, 7, 0, tzinfo=timezone.utc),
            news_type="Results & trading",
            direction="mixed",
            materiality=3,
            headline="Guidance unchanged",
            take=too_long,
        )


def test_invalid_materiality_is_rejected() -> None:
    with pytest.raises(ValueError, match="between 1 and 5"):
        materiality_circles(0)
