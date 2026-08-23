from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select

from analyst.classification import CANONICAL_RNS_TYPES
from analyst.version import ANALYSIS_VERSION, DEFAULT_PROMPT_VERSION
from database.company_intelligence import CompanyIntelligenceRepository
from database.db import create_database_engine, create_session_factory, init_database
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow
from database.product import ProductRepository
from database.db import session_scope
from product.formatting import feed_verdict, feed_view, public_rns_type
from settings import Settings

LONDON = ZoneInfo("Europe/London")
AcceptanceStatus = Literal["pass", "fail"]


@dataclass(frozen=True)
class AcceptanceCheck:
    code: str
    status: AcceptanceStatus
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _valid_http_url(value: object) -> bool:
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _as_london_day(value: datetime) -> object:
    parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LONDON).date()


def _latest_public_anchor(factory) -> dict[str, object] | None:
    with session_scope(factory) as session:
        row = session.execute(
            select(AnnouncementRow, CompanyRow, AnalystRunRow)
            .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
            .join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id)
            .where(
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
            )
            .order_by(desc(AnnouncementRow.published_at))
            .limit(1)
        ).first()
        if row is None:
            return None
        announcement, company, run = row
        return {
            "source_id": announcement.source_id,
            "ticker": company.ticker,
            "published_at": announcement.published_at,
            "analysis_version": run.analysis_version,
            "prompt_version": run.prompt_version,
        }


def _analyst32_contract_check(factory) -> AcceptanceCheck:
    with session_scope(factory) as session:
        rows = session.execute(
            select(AnnouncementRow, AnalystRunRow)
            .join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id)
            .where(
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.analysis_version == ANALYSIS_VERSION,
            )
        ).all()

    taxonomy_errors = [
        announcement.source_id
        for announcement, _run in rows
        if str(announcement.announcement_type or "") not in CANONICAL_RNS_TYPES
    ]
    prompt_errors = [
        announcement.source_id
        for announcement, run in rows
        if str(run.prompt_version or "") != DEFAULT_PROMPT_VERSION
    ]
    failures = list(dict.fromkeys([*taxonomy_errors, *prompt_errors]))
    return AcceptanceCheck(
        code="ANALYST32_CONTRACT",
        status="fail" if failures else "pass",
        message=(
            f"{len(failures)} current Analyst 3.2 record(s) violate taxonomy/version provenance."
            if failures
            else (
                f"{len(rows)} current Analyst 3.2 record(s) use the canonical taxonomy and prompt version."
                if rows
                else "No current Analyst 3.2 record exists yet; no incompatible 3.2 provenance is present."
            )
        ),
        details={
            "record_count": len(rows),
            "taxonomy_errors": taxonomy_errors[:20],
            "prompt_errors": prompt_errors[:20],
        },
    )


def run_release_acceptance(
    database_url: str,
    *,
    allow_sqlite: bool = False,
    require_public_data: bool = False,
) -> dict[str, object]:
    """Verify the public read path as one product journey without external calls.

    This intentionally tests the same data through Feed, Analyst Note and Company
    Intelligence read models. It complements the lower-level production audit by
    proving that one publishable announcement can traverse the complete investor
    journey and retain its source provenance.
    """

    checks: list[AcceptanceCheck] = []
    engine = create_database_engine(database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        product = ProductRepository(factory)
        intelligence = CompanyIntelligenceRepository(factory)

        dialect_ok = allow_sqlite or engine.dialect.name == "postgresql"
        checks.append(
            AcceptanceCheck(
                code="RELEASE_DATABASE",
                status="pass" if dialect_ok else "fail",
                message=(
                    f"Release acceptance is using {engine.dialect.name}."
                    if dialect_ok
                    else "Production release acceptance must use PostgreSQL."
                ),
            )
        )

        anchor = _latest_public_anchor(factory)
        if anchor is None:
            checks.append(
                AcceptanceCheck(
                    code="PUBLIC_DATA_ANCHOR",
                    status="fail" if require_public_data else "pass",
                    message=(
                        "No publishable announcement exists for the release journey."
                        if require_public_data
                        else "No publishable announcement exists; public-data journey was optional."
                    ),
                )
            )
        else:
            checks.append(
                AcceptanceCheck(
                    code="PUBLIC_DATA_ANCHOR",
                    status="pass",
                    message="A latest publishable announcement is available for end-to-end acceptance.",
                    details={
                        "source_id": str(anchor["source_id"]),
                        "ticker": str(anchor["ticker"]),
                        "published_at": str(anchor["published_at"]),
                    },
                )
            )

            day = _as_london_day(anchor["published_at"])  # type: ignore[arg-type]
            feed = product.list_feed(day, sort="impact")
            feed_ids = {str(item.get("source_id") or "") for item in feed}
            malformed_feed = [
                str(item.get("source_id") or "unknown")
                for item in feed
                if not str(item.get("ticker") or "").strip()
                or not str(item.get("headline") or "").strip()
                or not str(item.get("takeaway") or "").strip()
                or not _valid_http_url(item.get("source_url"))
            ]
            feed_ok = bool(feed) and str(anchor["source_id"]) in feed_ids and not malformed_feed
            checks.append(
                AcceptanceCheck(
                    code="FEED_READ_MODEL",
                    status="pass" if feed_ok else "fail",
                    message=(
                        f"Feed read model returned {len(feed)} publishable announcement(s) with source provenance."
                        if feed_ok
                        else "Feed read model is empty, missing the latest public record, or contains malformed public rows."
                    ),
                    details={"malformed_source_ids": malformed_feed[:20]},
                )
            )

            if feed:
                candidate = max(
                    feed,
                    key=lambda item: (
                        int(item.get("impact_score") or 0),
                        str(item.get("published_at") or ""),
                    ),
                )
                source_id = str(candidate.get("source_id") or "")
                ticker = str(candidate.get("ticker") or "")
                note = product.get_note(source_id, public_only=True)
                note_ok = bool(
                    note
                    and str(note.get("source_id") or "") == source_id
                    and str(note.get("ticker") or "") == ticker
                    and any(_valid_http_url(url) for url in list(note.get("source_urls") or []))
                )
                checks.append(
                    AcceptanceCheck(
                        code="ANALYST_NOTE_READ_MODEL",
                        status="pass" if note_ok else "fail",
                        message=(
                            "The selected Feed record resolves to a publishable Analyst Note with an original-source link."
                            if note_ok
                            else "The selected Feed record does not resolve cleanly to a public Analyst Note."
                        ),
                        details={"source_id": source_id, "ticker": ticker},
                    )
                )

                history = product.company_history(ticker)
                history_ids = {
                    str(item.get("source_id") or "")
                    for item in list((history or {}).get("announcements") or [])
                }
                history_ok = bool(history and source_id in history_ids)
                checks.append(
                    AcceptanceCheck(
                        code="COMPANY_HISTORY_READ_MODEL",
                        status="pass" if history_ok else "fail",
                        message=(
                            "The selected announcement is present in its public company history."
                            if history_ok
                            else "The selected announcement is missing from its public company history."
                        ),
                        details={"source_id": source_id, "ticker": ticker},
                    )
                )

                snapshot = intelligence.get_company_intelligence(ticker)
                impact_ids = {
                    str(item.get("source_id") or "")
                    for item in list((snapshot or {}).get("recent_impact_history") or [])
                }
                intelligence_ok = bool(
                    snapshot
                    and int(snapshot.get("announcement_count") or 0) >= 1
                    and source_id in impact_ids
                )
                checks.append(
                    AcceptanceCheck(
                        code="COMPANY_INTELLIGENCE_READ_MODEL",
                        status="pass" if intelligence_ok else "fail",
                        message=(
                            "Company Intelligence contains the selected announcement in its current memory snapshot."
                            if intelligence_ok
                            else "Company Intelligence could not carry the selected announcement into company memory."
                        ),
                        details={"source_id": source_id, "ticker": ticker},
                    )
                )

                verdict_feed = feed_verdict(candidate)
                verdict_note = feed_verdict(note or {})
                view_text = feed_view(candidate)
                presentation_ok = bool(
                    verdict_feed.strip()
                    and verdict_feed == verdict_note
                    and (int(candidate.get("impact_score") or 0) <= 1 or view_text.strip())
                    and public_rns_type(candidate.get("rns_type")) != "Other"
                )
                checks.append(
                    AcceptanceCheck(
                        code="PUBLIC_PRESENTATION_CONTRACT",
                        status="pass" if presentation_ok else "fail",
                        message=(
                            "Feed and Analyst Note resolve to the same verdict-first public presentation contract."
                            if presentation_ok
                            else "Verdict, interpretation or public taxonomy diverges across the Feed and Analyst Note."
                        ),
                        details={
                            "source_id": source_id,
                            "feed_verdict": verdict_feed,
                            "note_verdict": verdict_note,
                            "public_type": public_rns_type(candidate.get("rns_type")),
                        },
                    )
                )

        checks.append(_analyst32_contract_check(factory))

        failures = [check for check in checks if check.status == "fail"]
        return {
            "passed": not failures,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_dialect": engine.dialect.name,
            "expected_analysis_version": ANALYSIS_VERSION,
            "expected_prompt_version": DEFAULT_PROMPT_VERSION,
            "failure_count": len(failures),
            "checks": [check.as_dict() for check in checks],
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the complete public Smallcaps.ai read journey before release."
    )
    parser.add_argument(
        "--allow-sqlite",
        action="store_true",
        help="Permit SQLite for deterministic CI/preview acceptance.",
    )
    parser.add_argument(
        "--require-public-data",
        action="store_true",
        help="Fail when no publishable announcement is available for the journey.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    errors, runtime_warnings = settings.runtime_issues("web")
    if errors:
        payload: dict[str, Any] = {
            "passed": False,
            "runtime_errors": errors,
            "runtime_warnings": runtime_warnings,
        }
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        raise SystemExit(1)

    payload = run_release_acceptance(
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
