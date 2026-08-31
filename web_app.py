from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from streamlit.web.server.starlette import App as StreamlitApp

from api.company import create_company_routes
from api.daily_editor import create_daily_editor_routes
from api.frontend import create_frontend_routes
from api.monitoring import create_monitoring_routes
from api.newsroom import create_newsroom_routes

ROOT = Path(__file__).resolve().parent


class RevalidatingStaticFiles(StaticFiles):
    """Serve assets without allowing an old JavaScript contract to stay fresh.

    Customer HTML uses content-fingerprinted query strings. Revalidation is kept
    as a second line of defence for direct or previously unversioned asset URLs.
    """

    async def get_response(self, path: str, scope: dict[str, object]) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


# The Smallcaps.ai Company News and Company Intelligence surfaces are the public
# product. The existing Streamlit implementation remains available under
# /legacy during migration, while every surface uses the same PostgreSQL records.
legacy_app = StreamlitApp("streamlit_app.py")
app = Starlette(
    routes=[
        *create_frontend_routes(),
        *create_daily_editor_routes(),
        *create_newsroom_routes(),
        *create_monitoring_routes(),
        *create_company_routes(),
        Mount(
            "/assets",
            app=RevalidatingStaticFiles(directory=ROOT / "frontend" / "assets"),
            name="assets",
        ),
        Mount("/legacy", app=legacy_app, name="legacy"),
    ]
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8501")),
    )
