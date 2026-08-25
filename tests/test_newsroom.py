from __future__ import annotations

from datetime import date, datetime, time

from product.daily_editor import DailyEditorStory, build_daily_editor
from product.newsroom import (
    NewsroomFact,
    NewsroomMetricHistory,
    NewsroomNumberPoint,
    NewsroomStoryPacket,
    build_newsroom_article,
    build_newsroom_edition,
)


def story(*, source_id: str = "spr-update", ticker: str = "SPR", bucket: str = "also_matters") -> DailyEditorStory:
    return DailyEditorStory(
        story_key=f"{ticker}:trading:{source_id}",
        story_family="trading",
        primary_source_id=source_id,
        latest_source_id=source_id,
        source_ids=[source_id],
        ticker=ticker,
        company=f"{ticker} plc",
        first_published_at=datetime.fromisoformat("2026-08-25T07:10:00+01:00"),
        published_at=datetime.fromisoformat("2026-08-25T07:10:00+01:00"),
        bucket=bucket,  # type: ignore[arg-type]
        algorithmic_bucket=bucket if bucket != "lead" else "lead",  # type: ignore[arg-type]
        priority_score=52,
        ranking_reasons=["Impact 3/5."],
        rns_types=["Results & trading"],
        signal="GREEN",
        outlook="MAINTAINED",
        impact_score=3,
        editorial_headline="SPR cuts net debt again",
        why_it_matters="Good balance-sheet progress while earnings expectations remain intact.",
        what_changed="Net debt fell to £18.2m from £24.0m.",
        source_urls=[f"https://example.com/{source_id}"],
    )


def good_packet() -> NewsroomStoryPacket:
    item = story()
    return NewsroomStoryPacket(
        story=item,
        facts=[
            NewsroomFact(
                source_id="spr-update",
                source_url="https://example.com/spr-update",
                published_at="2026-08-25T07:10:00+01:00",
                label="Net debt",
                metric="Net debt",
                value="£18.2m",
                previous_value="£24.0m",
                comparator_source_id="spr-prior",
            )
        ],
        metric_history=[
            NewsroomMetricHistory(
                metric="Net debt",
                label="Net debt",
                direction="down",
                points=[
                    NewsroomNumberPoint(value="£29.8m", published_at="2025-12-10T07:00:00+00:00", source_id="spr-old", source_url="https://example.com/spr-old"),
                    NewsroomNumberPoint(value="£24.0m", published_at="2026-05-12T07:00:00+01:00", source_id="spr-prior", source_url="https://example.com/spr-prior"),
                    NewsroomNumberPoint(value="£18.2m", published_at="2026-08-25T07:10:00+01:00", source_id="spr-update", source_url="https://example.com/spr-update"),
                ],
            )
        ],
        watch_items=["Check cash conversion at the full-year results."],
        evidence_texts=["Net debt was £18.2m compared with £24.0m in May and £29.8m in December."],
        source_published_at={
            "spr-update": "2026-08-25T07:10:00+01:00",
            "spr-prior": "2026-05-12T07:00:00+01:00",
            "spr-old": "2025-12-10T07:00:00+00:00",
        },
        source_urls={
            "spr-update": "https://example.com/spr-update",
            "spr-prior": "https://example.com/spr-prior",
            "spr-old": "https://example.com/spr-old",
        },
    )


def test_newsroom_uses_structured_comparators_and_company_history() -> None:
    article = build_newsroom_article(good_packet())

    assert article.copydesk_status == "pass"
    assert "£18.2m" in article.news.text
    assert "£24.0m" in article.news.text
    assert article.the_number is not None
    assert [point.value for point in article.the_number.points] == ["£29.8m", "£24.0m", "£18.2m"]
    assert article.context
    assert "last three comparable disclosures" in article.context[0].text
    assert article.next_test is not None
    assert article.news.provenance[0].field_path == "facts"


def test_copydesk_fails_closed_on_unsupported_number() -> None:
    item = story(source_id="bad-update", ticker="BAD", bucket="quick_take")
    item = item.model_copy(update={"what_changed": "Revenue rose to £99m.", "editorial_headline": "BAD reports revenue growth", "why_it_matters": "Modestly positive update."})
    packet = NewsroomStoryPacket(
        story=item,
        evidence_texts=["Revenue rose to £10m."],
        source_published_at={"bad-update": "2026-08-25T07:10:00+01:00"},
        source_urls={"bad-update": "https://example.com/bad-update"},
    )

    article = build_newsroom_article(packet)

    assert article.copydesk_status == "fail"
    assert any(flag.startswith("UNSUPPORTED_NUMBER:£99m") for flag in article.copydesk_flags)


def test_failed_copydesk_story_is_withheld_from_edition() -> None:
    good = good_packet()
    editor_page = build_daily_editor(
        day=date(2026, 8, 25),
        cutoff=time(8, 0),
        candidates=[],
    ).model_copy(
        update={
            "candidate_count": 1,
            "published_story_count": 1,
            "other_analysed_count": 0,
            "lead": None,
            "also_matters": [good.story],
            "quick_takes": [],
            "quiet_morning": True,
        }
    )
    bad_story = good.story.model_copy(update={"what_changed": "Revenue rose to £99m."})
    bad = NewsroomStoryPacket(
        story=bad_story,
        evidence_texts=["Revenue rose to £10m."],
        source_published_at={"spr-update": "2026-08-25T07:10:00+01:00"},
        source_urls={"spr-update": "https://example.com/spr-update"},
    )
    edition = build_newsroom_edition(editor_page=editor_page, packets=[bad])

    assert edition.selected_story_count == 1
    assert edition.published_article_count == 0
    assert edition.withheld_story_count == 1
    assert edition.also_matters == []
