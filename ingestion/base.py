from __future__ import annotations

from typing import Protocol

from analyst.models import AnnouncementInput


class AnnouncementSource(Protocol):
    name: str

    def fetch_new(self) -> list[AnnouncementInput]: ...
