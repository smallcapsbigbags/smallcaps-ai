from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from streamlit.web.server.starlette import App as StreamlitApp

from api.company import create_company_routes
from api.daily_editor import create_daily_editor_routes
from api.frontend import create_frontend_routes
from api.monitoring import create_monitoring_routes
from api.newsroom import create_newsroom_routes

ROOT = Path(__file__).resolve().parent

# The SmallcapsBigBags-style monitoring sheet and Company Intelligence are the
# public product. The existing Streamlit implementation remains available under
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
            app=StaticFiles(directory=ROOT / "frontend" / "assets"),
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
