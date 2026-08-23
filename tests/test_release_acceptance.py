from pathlib import Path

from jobs.release_acceptance import run_release_acceptance
from jobs.seed_release_preview import seed as seed_release


def _sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def test_release_acceptance_passes_complete_seeded_product_journey(tmp_path: Path) -> None:
    database_url = _sqlite_url(tmp_path / "release.db")
    seed_release(database_url)

    report = run_release_acceptance(
        database_url,
        allow_sqlite=True,
        require_public_data=True,
    )

    assert report["passed"] is True, report
    assert report["failure_count"] == 0
    statuses = {
        check["code"]: check["status"]
        for check in report["checks"]
    }
    for code in (
        "RELEASE_DATABASE",
        "PUBLIC_DATA_ANCHOR",
        "FEED_READ_MODEL",
        "ANALYST_NOTE_READ_MODEL",
        "COMPANY_HISTORY_READ_MODEL",
        "COMPANY_INTELLIGENCE_READ_MODEL",
        "PUBLIC_PRESENTATION_CONTRACT",
        "ANALYST32_CONTRACT",
    ):
        assert statuses[code] == "pass"


def test_release_acceptance_fails_when_public_data_is_required_but_absent(tmp_path: Path) -> None:
    database_url = _sqlite_url(tmp_path / "empty.db")

    report = run_release_acceptance(
        database_url,
        allow_sqlite=True,
        require_public_data=True,
    )

    assert report["passed"] is False
    assert any(
        check["code"] == "PUBLIC_DATA_ANCHOR" and check["status"] == "fail"
        for check in report["checks"]
    )
