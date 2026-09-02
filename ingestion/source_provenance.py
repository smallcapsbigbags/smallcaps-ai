from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping
from urllib.parse import urlparse

from analyst.models import AnnouncementInput

FCA_HOSTS = {"data.fca.org.uk"}
OFFICIAL_RNS_HOSTS = {
    "londonstockexchange.com",
    "www.londonstockexchange.com",
    "rns.com",
    "www.rns.com",
    "lseg.com",
    "www.lseg.com",
}
MIRROR_HOSTS = {
    "lse.co.uk",
    "www.lse.co.uk",
    "investegate.co.uk",
    "www.investegate.co.uk",
}


def _clean_url(value: object) -> str:
    return str(value or "").strip()


def _host(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").lower()
    except ValueError:
        return ""


def valid_source_url(value: object) -> bool:
    url = _clean_url(value)
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def classify_source_url(value: object) -> str:
    url = _clean_url(value)
    if not valid_source_url(url):
        return "invalid"
    host = _host(url)
    if host in FCA_HOSTS:
        return "fca-nsm"
    if host in OFFICIAL_RNS_HOSTS:
        return "official-rns"
    if host in MIRROR_HOSTS:
        return "mirror"
    return "non-mirror"


def canonical_source_urls(values: Iterable[object]) -> list[str]:
    """Dedupe URLs and demote known mirrors behind stronger source classes."""

    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        url = _clean_url(value)
        if not valid_source_url(url) or url in seen:
            continue
        seen.add(url)
        deduped.append(url)

    rank = {
        "fca-nsm": 0,
        "official-rns": 1,
        "non-mirror": 2,
        "mirror": 3,
        "invalid": 4,
    }
    indexed = list(enumerate(deduped))
    indexed.sort(key=lambda pair: (rank[classify_source_url(pair[1])], pair[0]))
    return [url for _index, url in indexed]


@dataclass(frozen=True)
class SourceCoverage:
    status: str
    primary_url: str
    urls: tuple[str, ...]
    has_fca_nsm: bool
    has_official_rns: bool
    has_non_mirror: bool
    mirror_only: bool

    @property
    def note(self) -> str:
        if self.has_fca_nsm:
            return "Source verification: FCA NSM record present."
        if self.has_official_rns:
            return "Source verification: official RNS/London Stock Exchange record present."
        if self.has_non_mirror:
            return "Source verification: non-mirror source present."
        if self.mirror_only:
            return (
                "Source verification: mirror-only; an issuer, FCA NSM or official "
                "RNS source was not retained."
            )
        return "Source verification: no valid source URL retained."


def source_coverage(values: Iterable[object]) -> SourceCoverage:
    urls = canonical_source_urls(values)
    classes = {classify_source_url(url) for url in urls}
    has_fca = "fca-nsm" in classes
    has_rns = "official-rns" in classes
    has_non_mirror = bool(classes & {"fca-nsm", "official-rns", "non-mirror"})
    mirror_only = bool(urls) and classes == {"mirror"}
    if has_fca:
        status = "fca-nsm"
    elif has_rns:
        status = "official-rns"
    elif has_non_mirror:
        status = "non-mirror"
    elif mirror_only:
        status = "mirror-only"
    else:
        status = "missing"
    return SourceCoverage(
        status=status,
        primary_url=urls[0] if urls else "",
        urls=tuple(urls),
        has_fca_nsm=has_fca,
        has_official_rns=has_rns,
        has_non_mirror=has_non_mirror,
        mirror_only=mirror_only,
    )


def merge_source_note(existing: object, coverage: SourceCoverage) -> str:
    note = " ".join(str(existing or "").strip().split())
    if "Source verification:" in note:
        note = note.split("Source verification:", 1)[0].strip()
    return " ".join(part for part in (note, coverage.note) if part).strip()


def normalise_announcement_provenance(
    announcement: AnnouncementInput,
) -> AnnouncementInput:
    coverage = source_coverage(
        [*announcement.source_urls, announcement.source_url]
    )
    return announcement.model_copy(
        update={
            "source_url": coverage.primary_url,
            "source_urls": list(coverage.urls),
            "source_note": merge_source_note(announcement.source_note, coverage),
        }
    )


def provenance_counts(
    source_urls_by_id: Mapping[str, Iterable[object]],
) -> dict[str, int]:
    counts = {
        "fca_nsm": 0,
        "official_rns": 0,
        "non_mirror": 0,
        "mirror_only": 0,
        "missing": 0,
    }
    for values in source_urls_by_id.values():
        status = source_coverage(values).status.replace("-", "_")
        if status in counts:
            counts[status] += 1
    return counts
