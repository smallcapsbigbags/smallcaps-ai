from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

VALID_AIM_DISCOVERY_MODES: Final[tuple[str, ...]] = (
    "disabled",
    "licensed",
    "owner-test",
)


def normalise_aim_discovery_mode(value: object) -> str:
    cleaned = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "off": "disabled",
        "none": "disabled",
        "licensed-feed": "licensed",
        "licensed-source": "licensed",
        "owner": "owner-test",
        "test": "owner-test",
        "private-beta": "owner-test",
    }
    return aliases.get(cleaned, cleaned or "disabled")


def _is_https_or_local(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme == "https" and parsed.netloc:
        return True
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and bool(parsed.netloc)
    )


@dataclass(frozen=True)
class AIMSourcePolicy:
    """Fail-closed policy for the AIM announcement discovery boundary."""

    mode: str
    licensed_feed_url: str = ""
    allow_unlicensed_owner_test_catalogues: bool = False
    private_beta_mode: bool = False
    running_on_railway: bool = False

    @property
    def normalised_mode(self) -> str:
        return normalise_aim_discovery_mode(self.mode)

    @property
    def enabled(self) -> bool:
        return self.normalised_mode != "disabled"

    @property
    def public_launch_ready(self) -> bool:
        return (
            self.normalised_mode == "licensed"
            and _is_https_or_local(self.licensed_feed_url)
        )

    def issues(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        mode = self.normalised_mode

        if mode not in VALID_AIM_DISCOVERY_MODES:
            errors.append(
                "AIM_DISCOVERY_MODE must be one of "
                + ", ".join(VALID_AIM_DISCOVERY_MODES)
                + f"; received {self.mode!r}."
            )
            return errors, warnings

        if mode == "disabled":
            warnings.append(
                "AIM discovery is disabled. Existing company repositories remain "
                "available, but no new announcements will be discovered."
            )
            return errors, warnings

        if mode == "licensed":
            if not self.licensed_feed_url.strip():
                errors.append(
                    "AIM_DISCOVERY_MODE=licensed requires AIM_LICENSED_FEED_URL."
                )
            elif not _is_https_or_local(self.licensed_feed_url):
                errors.append(
                    "AIM_LICENSED_FEED_URL must use HTTPS "
                    "(HTTP is allowed only for localhost tests)."
                )
            return errors, warnings

        # owner-test is deliberately explicit and cannot become a public launch mode.
        if not self.private_beta_mode:
            errors.append(
                "AIM_DISCOVERY_MODE=owner-test is permitted only while "
                "PRIVATE_BETA_MODE=true."
            )
        if not self.allow_unlicensed_owner_test_catalogues:
            errors.append(
                "AIM_DISCOVERY_MODE=owner-test requires the explicit "
                "ALLOW_UNLICENSED_OWNER_TEST_CATALOGUES=true acknowledgement."
            )
        warnings.append(
            "Owner-test discovery uses private-investor web catalogues. It is "
            "not approved for a public or commercial launch; configure a licensed "
            "feed before disabling private beta."
        )
        return errors, warnings

    def summary(self) -> dict[str, object]:
        errors, warnings = self.issues()
        return {
            "mode": self.normalised_mode,
            "enabled": self.enabled,
            "public_launch_ready": self.public_launch_ready,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }
