from __future__ import annotations

"""Schema-tolerant loader for the Phase 3 company-memory page.

The production database already contains structured companies, announcements,
analyst runs, facts, guidance and management claims. This adapter reads those
records without creating a second source of truth or requiring a historical AI
backfill.
"""

from datetime import datetime
from typing import Any, Iterable, Mapping

from sqlalchemy import Engine, inspect, text

from analyst.company_memory import CompanyMemorySnapshot, build_company_memory

_TABLE_CANDIDATES = {
    "companies": ("companies", "company"),
    "announcements": ("announcements", "announcement"),
    "runs": ("analyst_runs", "analyst_run", "analysis_runs"),
    "facts": ("facts", "fact"),
    "guidance": ("guidance_events", "guidance_event", "guidance"),
    "claims": ("management_claims", "management_claim", "claims"),
}


def _resolve_table(table_names: Iterable[str], candidates: Iterable[str]) -> str | None:
    available = list(table_names)
    lowered = {name.lower(): name for name in available}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    for candidate in candidates:
        for name in available:
            if candidate in name.lower():
                return name
    return None


def _rows(connection, table: str | None) -> list[dict[str, Any]]:
    if not table:
        return []
    preparer = connection.dialect.identifier_preparer
    quoted = preparer.quote(table)
    result = connection.execute(text(f"SELECT * FROM {quoted}"))
    return [dict(row._mapping) for row in result]


def _first(row: Mapping[str, Any], *keys: str) -> Any:
    lower = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lower.get(key.lower())
        if value is not None and value != "":
            return value
    return None


def _normal(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _matches(value: Any, target: Any) -> bool:
    return _normal(value).lower() == _normal(target).lower()


def list_covered_companies(engine: Engine) -> list[dict[str, str]]:
    inspector = inspect(engine)
    table = _resolve_table(
        inspector.get_table_names(), _TABLE_CANDIDATES["companies"]
    )
    with engine.connect() as connection:
        rows = _rows(connection, table)
    output: list[dict[str, str]] = []
    for row in rows:
        ticker = _normal(_first(row, "ticker", "epic", "symbol"))
        company = _normal(
            _first(row, "name", "company", "company_name", "issuer_name")
        )
        if ticker:
            output.append(
                {"ticker": ticker.upper(), "company": company or ticker.upper()}
            )
    return sorted(output, key=lambda item: (item["company"].lower(), item["ticker"]))


def load_company_memory_from_database(
    engine: Engine,
    *,
    ticker: str,
    as_of: datetime | None = None,
) -> CompanyMemorySnapshot:
    inspector = inspect(engine)
    names = inspector.get_table_names()
    resolved = {
        key: _resolve_table(names, candidates)
        for key, candidates in _TABLE_CANDIDATES.items()
    }
    with engine.connect() as connection:
        raw = {key: _rows(connection, table) for key, table in resolved.items()}

    company_row = next(
        (
            row
            for row in raw["companies"]
            if _matches(_first(row, "ticker", "epic", "symbol"), ticker)
        ),
        None,
    )
    company_id = _first(company_row or {}, "id", "company_id")
    company_name = _normal(
        _first(
            company_row or {},
            "name",
            "company",
            "company_name",
            "issuer_name",
        )
    ) or ticker.upper()

    announcements: list[dict[str, Any]] = []
    announcement_ids: set[str] = set()
    for row in raw["announcements"]:
        row_company_id = _first(row, "company_id", "issuer_id")
        row_ticker = _first(row, "ticker", "epic", "symbol")
        if company_id is not None:
            belongs = _matches(row_company_id, company_id)
        else:
            belongs = _matches(row_ticker, ticker)
        if not belongs:
            continue
        item = dict(row)
        row_id = _first(row, "id", "announcement_id")
        source_id = _first(row, "source_id", "rns_id", "external_id")
        if row_id is not None:
            announcement_ids.add(_normal(row_id))
        if source_id is not None:
            announcement_ids.add(_normal(source_id))
        item.setdefault("source_id", source_id or row_id)
        item.setdefault(
            "published_at",
            _first(row, "published_at", "announcement_date", "created_at"),
        )
        item.setdefault(
            "title", _first(row, "title", "headline", "announcement_title")
        )
        announcements.append(item)

    run_by_id: dict[str, dict[str, Any]] = {}
    run_by_announcement: dict[str, dict[str, Any]] = {}
    for row in raw["runs"]:
        announcement_ref = _normal(
            _first(row, "announcement_id", "source_id", "announcement_source_id")
        )
        if announcement_ref not in announcement_ids:
            continue
        is_current = _first(row, "is_current", "current")
        if is_current is not None and str(is_current).lower() in {
            "false",
            "0",
            "no",
        }:
            continue
        item = dict(row)
        run_id = _normal(_first(row, "id", "analyst_run_id", "run_id"))
        if run_id:
            run_by_id[run_id] = item
        run_by_announcement[announcement_ref] = item

    for announcement in announcements:
        refs = {
            _normal(_first(announcement, "id", "announcement_id")),
            _normal(_first(announcement, "source_id", "rns_id", "external_id")),
        }
        run = next(
            (run_by_announcement[ref] for ref in refs if ref in run_by_announcement),
            {},
        )
        for source, target in (
            ("headline", "analysis_headline"),
            ("takeaway", "takeaway"),
            ("analyst_view", "analyst_view"),
            ("impact_rationale", "impact_rationale"),
            ("impact_colour", "impact_colour"),
            ("impact_score", "impact_score"),
        ):
            value = _first(run, source)
            if value is not None:
                announcement[target] = value

    announcement_by_ref: dict[str, dict[str, Any]] = {}
    for announcement in announcements:
        for key in (
            "id",
            "announcement_id",
            "source_id",
            "rns_id",
            "external_id",
        ):
            value = _first(announcement, key)
            if value is not None:
                announcement_by_ref[_normal(value)] = announcement

    def child_rows(kind: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for row in raw[kind]:
            run_ref = _normal(_first(row, "analyst_run_id", "run_id"))
            announcement_ref = _normal(
                _first(
                    row,
                    "announcement_id",
                    "source_id",
                    "announcement_source_id",
                )
            )
            run = run_by_id.get(run_ref, {})
            if not announcement_ref:
                announcement_ref = _normal(
                    _first(
                        run,
                        "announcement_id",
                        "source_id",
                        "announcement_source_id",
                    )
                )
            announcement = announcement_by_ref.get(announcement_ref)
            if announcement is None:
                continue
            item = dict(row)
            item.setdefault(
                "source_id", _first(announcement, "source_id", "id")
            )
            item.setdefault(
                "published_at",
                _first(announcement, "published_at", "announcement_date"),
            )
            item.setdefault(
                "source_title", _first(announcement, "title", "headline")
            )
            output.append(item)
        return output

    return build_company_memory(
        ticker=ticker,
        company=company_name,
        announcements=announcements,
        facts=child_rows("facts"),
        guidance=child_rows("guidance"),
        management_claims=child_rows("claims"),
        as_of=as_of,
    )
