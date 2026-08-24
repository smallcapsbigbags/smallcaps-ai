from __future__ import annotations

import os

from streamlit.web.server.starlette import App

from api.monitoring import create_monitoring_routes

# Streamlit 1.60 exposes an ASGI-compatible App with first-class custom routes.
# One process therefore serves the existing product and the read-only monitoring API
# without adding a fourth Railway service or a second database connection boundary.
app = App(
    "streamlit_app.py",
    routes=create_monitoring_routes(),
)


if __name__ == "__main__":
    app.run(
        config={
            "server.address": "0.0.0.0",
            "server.port": int(os.getenv("PORT", "8501")),
            "server.headless": True,
        }
    )
