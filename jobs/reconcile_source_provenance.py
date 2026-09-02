from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from sqlalchemy import select

from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from database.models import AnnouncementRow
from ingestion.source_provenance import (
    canonical_source_urls,
    source_coverage,
)
from settings import Settings


@dataclass
class ReconciliationSummary:
    scanned: int = 0
    reordered: int = 0
    fca_nsm: int = 0
    official_rns: int = 0
    non_mirror: int = 0
    mirror_only: int = 0
    missing: int = 0


def reconcile_source_provenance(
    session_factory,
    *,
    apply: bool = False,
) -> ReconciliationSummary:
    summary = ReconciliationSummary()
    with session_scope(session_factory) as session:
        rows = session.scalars(
            select(AnnouncementRow).order_by(
                AnnouncementRow.published_at,
                AnnouncementRow.source_id,
            )
        ).all()
        for row in rows:
            summary.scanned += 1
            existing = [
                *(
                    row.source_urls
                    if isinstance(row.source_urls, list)
                    else []
                ),
                row.source_url,
            ]
            urls = canonical_source_urls(existing)
            coverage = source_coverage(urls)
            key = coverage.status.replace("-", "_")
            if hasattr(summary, key):
                setattr(summary, key, getattr(summary, key) + 1)

            changed = (
                list(row.source_urls or []) != urls
                or row.source_url != coverage.primary_url
            )
            if changed:
                summary.reordered += 1
                if apply:
                    row.source_urls = urls
                    row.source_url = coverage.primary_url
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit and normalise retained announcement source URLs."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist canonical URL ordering and primary source_url.",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    engine = create_database_engine(settings.database_url)
    try:
        init_database(engine)
        factory = create_session_factory(engine)
        summary = reconcile_source_provenance(factory, apply=args.apply)
        print(
            json.dumps(
                {
                    **asdict(summary),
                    "applied": args.apply,
                    "schema_version": "source-provenance-v1",
                },
                indent=2,
                sort_keys=True,
            ),
            flush=True,
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
