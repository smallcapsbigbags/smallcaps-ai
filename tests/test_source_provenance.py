from __future__ import annotations

from datetime import datetime, timezone

from analyst.models import AnnouncementInput
from ingestion.source_provenance import (
    canonical_source_urls,
    classify_source_url,
    normalise_announcement_provenance,
    provenance_counts,
    source_coverage,
)


def test_source_classes_and_canonical_order() -> None:
    mirror = "https://www.lse.co.uk/rns/ABC/example.html"
    other = "https://www.exampleplc.com/investors/rns/example"
    official = "https://www.londonstockexchange.com/news-article/abc/example/1"
    fca = "https://data.fca.org.uk/artefacts/NSM/RNS/example.html"

    urls = canonical_source_urls([mirror, other, official, fca, mirror])

    assert urls == [fca, official, other, mirror]
    assert classify_source_url(fca) == "fca-nsm"
    assert classify_source_url(mirror) == "mirror"


def test_announcement_provenance_demotes_mirrors_and_records_status() -> None:
    announcement = AnnouncementInput(
        source_id="aim-test",
        ticker="ABC",
        company="Example plc",
        published_at=datetime(2026, 9, 2, 7, 0, tzinfo=timezone.utc),
        title="Trading Update",
        text="Example plc reported revenue of £10m.",
        source_url="https://www.lse.co.uk/rns/ABC/example.html",
        source_urls=[
            "https://www.lse.co.uk/rns/ABC/example.html",
            "https://data.fca.org.uk/artefacts/NSM/RNS/example.html",
        ],
        source_note="Matched company, date and headline.",
    )

    normalised = normalise_announcement_provenance(announcement)

    assert normalised.source_url.startswith("https://data.fca.org.uk/")
    assert normalised.source_urls[-1].startswith("https://www.lse.co.uk/")
    assert "FCA NSM record present" in normalised.source_note


def test_mirror_only_is_not_described_as_verified() -> None:
    coverage = source_coverage(
        ["https://www.investegate.co.uk/announcement/example"]
    )

    assert coverage.status == "mirror-only"
    assert coverage.mirror_only
    assert "mirror-only" in coverage.note


def test_provenance_counts_one_status_per_source_record() -> None:
    counts = provenance_counts(
        {
            "fca": [
                "https://data.fca.org.uk/artefacts/NSM/RNS/example.html",
                "https://www.lse.co.uk/rns/ABC/example.html",
            ],
            "official": [
                "https://www.londonstockexchange.com/news-article/a/b/1"
            ],
            "mirror": [
                "https://www.investegate.co.uk/announcement/example"
            ],
            "missing": [],
        }
    )

    assert counts == {
        "fca_nsm": 1,
        "official_rns": 1,
        "non_mirror": 0,
        "mirror_only": 1,
        "missing": 1,
    }
