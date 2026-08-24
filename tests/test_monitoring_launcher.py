from __future__ import annotations

import json
from pathlib import Path


def test_production_launcher_mounts_api_without_a_fourth_service() -> None:
    source = Path("web_app.py").read_text(encoding="utf-8")
    assert "App(" in source
    assert '"streamlit_app.py"' in source
    assert "create_monitoring_routes()" in source

    railway = json.loads(Path("railway.json").read_text(encoding="utf-8"))
    start = railway["deploy"]["startCommand"]
    assert "uvicorn web_app:app" in start
    assert railway["deploy"]["healthcheckPath"] == "/api/v1/health"
    predeploy = " ".join(railway["deploy"]["preDeployCommand"])
    assert "jobs.monitoring_acceptance --require-public-data" in predeploy


def test_ci_compiles_new_api_and_launcher_surfaces() -> None:
    workflow = Path(".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "compileall analyst api database" in workflow
    assert "web_app.py" in workflow


def test_asgi_dependencies_are_directly_locked() -> None:
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    assert "starlette==1.6.0" in requirements
    assert "uvicorn==0.52.4" in requirements
