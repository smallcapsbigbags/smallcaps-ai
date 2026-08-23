from __future__ import annotations

import os

from analyst.version import DEFAULT_PROMPT_VERSION
from jobs import seed_launch_preview, seed_pass1_preview


def seed(database_url: str) -> None:
    """Build the visual fixtures with the currently shipped prompt provenance.

    The Pass 1/launch seed modules intentionally preserve their historical fixture
    definitions. Release acceptance reuses those records but stamps them with the
    current prompt contract so provenance checks exercise the release version.
    """

    seed_launch_preview.PROMPT_VERSION = DEFAULT_PROMPT_VERSION
    seed_pass1_preview.PROMPT_VERSION = DEFAULT_PROMPT_VERSION
    seed_launch_preview.seed(database_url)
    seed_pass1_preview.seed(database_url)


if __name__ == "__main__":
    seed(os.getenv("DATABASE_URL", "sqlite+pysqlite:///data/release-acceptance.db"))
