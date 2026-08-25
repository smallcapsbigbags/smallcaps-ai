from pathlib import Path

from jobs.daily_editor_acceptance import run_daily_editor_acceptance
from jobs.seed_release_preview import seed as seed_release


def _sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path}"


def test_daily_editor_acceptance_passes_seeded_public_data(tmp_path: Path) -> None:
    database_url = _sqlite_url(tmp_path / "daily-editor.db")
    seed_release(database_url)

    report = run_daily_editor_acceptance(
        database_url,
        allow_sqlite=True,
        require_public_data=True,
    )

    assert report["passed"] is True, report
    assert report["failure_count"] == 0
    statuses = {check["code"]: check["status"] for check in report["checks"]}
    assert statuses["AIM_DAILY_DATABASE"] == "pass"
    assert statuses["AIM_DAILY_EDITOR_READ_MODEL"] == "pass"


def test_daily_editor_acceptance_fails_when_full_public_data_is_required_but_absent(tmp_path: Path) -> None:
    database_url = _sqlite_url(tmp_path / "empty-daily-editor.db")

    report = run_daily_editor_acceptance(
        database_url,
        allow_sqlite=True,
        require_public_data=True,
    )

    assert report["passed"] is False
    assert any(
        check["code"] == "AIM_DAILY_PUBLIC_DATA" and check["status"] == "fail"
        for check in report["checks"]
    )
