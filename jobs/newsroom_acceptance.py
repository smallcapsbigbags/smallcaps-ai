from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select

from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.editorial_calibration import EditorialCalibrationRepository
from database.models import AnalystRunRow, AnnouncementRow
from database.newsroom import NewsroomRepository
from product.newsroom import NEWSROOM_SCHEMA_VERSION, NEWSROOM_VERSION, NewsroomArticle
from settings import Settings

LONDON = ZoneInfo("Europe/London")


def _valid_http_url(value: object) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _latest_full_public_day(factory):
    with session_scope(factory) as session:
        row = session.execute(
            select(AnnouncementRow.published_at, AnnouncementRow.source_id)
            .join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id)
            .where(
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
                ~AnalystRunRow.model_version.like("deterministic-metadata%"),
            )
            .order_by(desc(AnnouncementRow.published_at))
            .limit(1)
        ).first()
    if row is None:
        return None
    published_at, source_id = row
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at.astimezone(LONDON).date(), str(source_id)


def _articles(edition) -> list[NewsroomArticle]:
    return [
        *([edition.lead] if edition.lead is not None else []),
        *edition.also_matters,
        *edition.quick_takes,
    ]


def run_newsroom_acceptance(
    database_url: str,
    *,
    allow_sqlite: bool = False,
    require_public_data: bool = False,
) -> dict[str, object]:
    engine = create_database_engine(database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        dialect_ok = allow_sqlite or engine.dialect.name == "postgresql"
        anchor = _latest_full_public_day(factory)
        checks: list[dict[str, object]] = [
            {
                "code": "AIM_DAILY_NEWSROOM_DATABASE",
                "status": "pass" if dialect_ok else "fail",
                "message": (
                    f"AIM Daily newsroom acceptance is using {engine.dialect.name}."
                    if dialect_ok
                    else "Production AIM Daily newsroom acceptance must use PostgreSQL."
                ),
            }
        ]

        if anchor is None:
            checks.append(
                {
                    "code": "AIM_DAILY_NEWSROOM_PUBLIC_DATA",
                    "status": "fail" if require_public_data else "pass",
                    "message": (
                        "No publication-safe FULL analysis exists for the newsroom."
                        if require_public_data
                        else "No publication-safe FULL analysis exists; data was optional."
                    ),
                }
            )
        else:
            day, anchor_source_id = anchor
            story_links_created = EditorialCalibrationRepository(factory).ensure_story_links(day)
            edition = NewsroomRepository(factory).get_edition(day, cutoff=time(23, 59))
            articles = _articles(edition)
            malformed: list[str] = []
            for article in articles:
                claims = [article.news, *article.context, article.view]
                if article.the_catch is not None:
                    claims.append(article.the_catch)
                claims.extend(article.whats_missing)
                if article.next_test is not None:
                    claims.append(article.next_test)
                if (
                    article.copydesk_status != "pass"
                    or article.copydesk_flags
                    or not article.headline.strip()
                    or not article.news.text.strip()
                    or not article.view.text.strip()
                    or not article.source_ids
                    or not article.source_urls
                    or not all(_valid_http_url(url) for url in article.source_urls)
                    or any(not claim.provenance for claim in claims)
                ):
                    malformed.append(article.story_key)

            count_ok = (
                edition.published_article_count == len(articles)
                and edition.withheld_story_count
                == edition.selected_story_count - edition.published_article_count
                and edition.selected_story_count >= edition.published_article_count
            )
            publication_ok = (
                edition.selected_story_count == 0
                or edition.published_article_count >= 1
            )
            contract_ok = (
                edition.schema_version == NEWSROOM_SCHEMA_VERSION
                and edition.newsroom_version == NEWSROOM_VERSION
                and count_ok
                and publication_ok
                and not malformed
            )
            checks.append(
                {
                    "code": "AIM_DAILY_NEWSROOM_READ_MODEL",
                    "status": "pass" if contract_ok else "fail",
                    "message": (
                        f"Newsroom published {edition.published_article_count} copy-desk-passed article(s) from {edition.selected_story_count} selected editor story/stories."
                        if contract_ok
                        else "Newsroom contract, provenance or copy-desk publication gate failed."
                    ),
                    "details": {
                        "date": day.isoformat(),
                        "anchor_source_id": anchor_source_id,
                        "story_links_created": story_links_created,
                        "screened_candidate_count": edition.screened_candidate_count,
                        "selected_story_count": edition.selected_story_count,
                        "published_article_count": edition.published_article_count,
                        "withheld_story_count": edition.withheld_story_count,
                        "malformed_story_keys": malformed,
                    },
                }
            )

        failures = [item for item in checks if item["status"] == "fail"]
        return {
            "passed": not failures,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_dialect": engine.dialect.name,
            "schema_version": NEWSROOM_SCHEMA_VERSION,
            "newsroom_version": NEWSROOM_VERSION,
            "failure_count": len(failures),
            "checks": checks,
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the evidence-bound AIM Daily newsroom read model.")
    parser.add_argument("--allow-sqlite", action="store_true")
    parser.add_argument("--require-public-data", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, runtime_warnings = settings.runtime_issues("web")
    if errors:
        payload: dict[str, object] = {
            "passed": False,
            "runtime_errors": errors,
            "runtime_warnings": runtime_warnings,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        raise SystemExit(1)

    payload = run_newsroom_acceptance(
        settings.database_url,
        allow_sqlite=args.allow_sqlite,
        require_public_data=args.require_public_data,
    )
    payload["runtime_warnings"] = runtime_warnings
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
