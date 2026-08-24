from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from streamlit.web.server.starlette import App as StreamlitApp

from api.frontend import create_frontend_routes
from api.monitoring import create_monitoring_routes

ROOT = Path(__file__).resolve().parent

# The exact SmallcapsBigBags-style monitoring sheet is now the public root. The
# existing Streamlit product remains available under /legacy during migration, while
# both surfaces and the versioned API continue to use the same PostgreSQL database.
legacy_app = StreamlitApp("streamlit_app.py")
app = Starlette(
    routes=[
        *create_frontend_routes(),
        *create_monitoring_routes(),
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
