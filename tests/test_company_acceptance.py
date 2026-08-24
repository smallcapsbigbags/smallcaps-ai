from __future__ import annotations

from jobs.company_acceptance import run_company_acceptance
from jobs.seed_launch_preview import seed as seed_launch_preview
from jobs.seed_pass1_preview import seed as seed_pass1_preview


def test_company_acceptance_passes_for_public_preview_data(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'company-acceptance.db'}"
    seed_launch_preview(database_url)
    seed_pass1_preview(database_url)

    payload = run_company_acceptance(
        database_url,
        allow_sqlite=True,
        require_public_data=True,
    )

    assert payload["passed"] is True
    assert payload["failure_count"] == 0
    assert payload["schema_version"] == "scbb-company-v1"
    statuses = {check["code"]: check["status"] for check in payload["checks"]}
    assert statuses == {
        "COMPANY_SHEET_DATABASE": "pass",
        "COMPANY_SHEET_CURRENT_POSITION": "pass",
        "COMPANY_SHEET_RNS_HISTORY": "pass",
        "COMPANY_SHEET_METRIC_DISCIPLINE": "pass",
        "COMPANY_SHEET_SOURCE_PROVENANCE": "pass",
    }


def test_company_acceptance_can_allow_an_empty_optional_database(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'empty-company-acceptance.db'}"

    payload = run_company_acceptance(
        database_url,
        allow_sqlite=True,
        require_public_data=False,
    )

    assert payload["passed"] is True
    assert payload["checks"][-1]["code"] == "COMPANY_SHEET_PUBLIC_ANCHOR"
    assert payload["checks"][-1]["status"] == "pass"
