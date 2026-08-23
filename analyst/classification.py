from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol


class AnnouncementLike(Protocol):
    title: str
    categories: list[str]


CANONICAL_RNS_TYPES: tuple[str, ...] = (
    "Funding & solvency",
    "Results & trading",
    "Fundraising",
    "Contracts",
    "Acquisition",
    "Disposal",
    "Takeover",
    "Operations",
    "Holdings",
    "Director dealing",
    "Share capital",
    "Remuneration",
    "Board & advisers",
    "Partnerships",
    "Listing status",
    "Corporate",
    "Other",
)

ADMINISTRATIVE_PATTERNS = [
    r"\btotal voting rights\b",
    r"\btransaction in own shares\b",
    r"\bblock listing(?: six monthly return| interim review)?\b",
    r"\bnotice of agm\b",
    r"\bresults? of agm\b",
    r"\bannual report and accounts\b",
    r"\bpublication of annual report\b",
    r"\bchange of registered office\b",
    r"\bchange of adviser\b",
    r"\bnotice of results\b",
]

OWNERSHIP_PATTERNS = [
    r"\btr-?1\b",
    r"\bholding(?:\(s\)|s)? in company\b",
    r"\bmajor holding\b",
    r"\bnotification of major holdings\b",
    r"\bdirector dealing\b",
    r"\bpdmr\b",
    r"\bnotification of transactions?\b",
    r"\btransaction by (?:a )?(?:director|pdmr)\b",
]

# These patterns deliberately require evidence of financial distress rather than
# treating every reference to debt, funding or the normal going-concern basis as
# a solvency event.
SOLVENCY_PATTERNS = [
    r"\bnotice of intention to appoint administrators?\b",
    r"\b(?:intend|intends|intended|will|expects?) to appoint administrators?\b",
    r"\badministrators? (?:have been |has been |were |was )?appointed\b",
    r"\bappointment of administrators?\b",
    r"\benter(?:ed|ing)? administration\b",
    r"\b(?:insolvent|insolvency|liquidation|winding[- ]up)\b",
    r"\bmaterial uncertainty\b.{0,120}\bgoing concern\b",
    r"\bgoing concern\b.{0,120}\bmaterial uncertainty\b",
    r"\b(?:unable|insufficient funds?)\b.{0,120}\bgoing concern\b",
    r"\bgoing concern\b.{0,120}\b(?:unable|insufficient funds?)\b",
    r"\binsufficient working capital\b",
    r"\bworking capital (?:shortfall|deficit)\b",
    r"\bcovenants?\b.{0,100}\b(?:breach|breached|waiver|non[- ]compliance|not compliant)\b",
    r"\b(?:breach|breached)\b.{0,100}\bcovenants?\b",
    r"\b(?:repayable|payable|due) on demand\b",
    r"\b(?:emergency|rescue) (?:finance|financing|funding)\b",
    r"\b(?:requires?|will require|needs?|will need) (?:additional |further )?(?:funding|finance|capital)\b",
    r"\bfunding (?:shortfall|gap|requirement)\b",
    r"\brefinanc\w*\b.{0,100}\b(?:deadline|maturity|matures|before|by)\b",
]

MATERIAL_PATTERNS = [
    *SOLVENCY_PATTERNS,
    r"\btrading update\b",
    r"\btrading statement\b",
    r"\bprofit warning\b",
    r"\bguidance\b",
    r"\bfinal results\b",
    r"\binterim results\b",
    r"\bhalf[- ]year results\b",
    r"\bfull[- ]year results\b",
    r"\bannual results\b",
    r"\bcontract(?: win| award| loss)?\b",
    r"\border(?: win| award)?\b",
    r"\bacquisition\b",
    r"\bdisposal\b",
    r"\bplacing\b",
    r"\bfundrais(?:e|ing)\b",
    r"\bsubscription\b",
    r"\bretail offer\b",
    r"\bdebt\b",
    r"\bloan\b",
    r"\bfacility\b",
    r"\bstrategic review\b",
    r"\boperational update\b",
    r"\bproduction update\b",
    r"\bresource update\b",
    r"\bdrilling\b",
    r"\bclinical trial\b",
    r"\bregulatory approval\b",
    r"\bfda\b",
    r"\bsuspension\b",
    r"\brestoration\b",
    r"\boffer\b",
    r"\btakeover\b",
    r"\bmerger\b",
    r"\bscheme of arrangement\b",
    r"\bshare buyback programme\b",
    r"\bcapital return\b",
    r"\bchief executive\b",
    r"\bchief financial officer\b",
    r"\bceo\b",
    r"\bcfo\b",
]


def _matches(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _announcement_text(announcement: AnnouncementLike) -> str:
    # Catalogue rows have title/categories only. Fully retrieved AnnouncementInput
    # objects also expose text, which lets the canonical taxonomy use the actual
    # RNS evidence without requiring another model call.
    evidence = str(getattr(announcement, "text", "") or "")
    return " ".join([announcement.title, *announcement.categories, evidence])


def is_administrative_routine(announcement: AnnouncementLike) -> bool:
    """Match current RNS-Xray behaviour: ownership notices are not auto-routine."""

    text = _announcement_text(announcement)
    if _matches(MATERIAL_PATTERNS, text) or _matches(OWNERSHIP_PATTERNS, text):
        return False
    if _matches(ADMINISTRATIVE_PATTERNS, text):
        return True
    categories = " ".join(announcement.categories).lower()
    return any(
        marker in categories
        for marker in (
            "total voting rights",
            "transaction in own shares",
            "block listing",
            "notice of meeting",
            "annual report publication",
        )
    )


def material_priority(announcement: AnnouncementLike) -> int:
    text = _announcement_text(announcement)
    if _matches(SOLVENCY_PATTERNS, text):
        return 100
    if _matches(MATERIAL_PATTERNS, text):
        return 90
    if _matches(OWNERSHIP_PATTERNS, text):
        return 62
    if not is_administrative_routine(announcement):
        return 38
    return 5


def classify_metadata_type(announcement: AnnouncementLike) -> str:
    """Return the canonical public taxonomy from title/categories/evidence.

    The ordering is intentional. Solvency distress dominates fundraising language,
    and takeover/acquisition/disposal events are separated before generic corporate
    labels. The function remains conservative: if no rule is supported it returns
    ``Other`` rather than guessing.
    """

    text = _announcement_text(announcement)
    if _matches(SOLVENCY_PATTERNS, text):
        return "Funding & solvency"

    rules: list[tuple[str, tuple[str, ...]]] = [
        (
            "Takeover",
            (
                r"\bpossible offer\b",
                r"\bfirm offer\b",
                r"\btakeover\b",
                r"\bmerger\b",
                r"\bscheme of arrangement\b",
                r"\brule 2\.[467]\b",
            ),
        ),
        (
            "Fundraising",
            (
                r"\bplacing\b",
                r"\bfundrais(?:e|ing)\b",
                r"\bsubscription\b",
                r"\bretail offer\b",
                r"\bopen offer\b",
            ),
        ),
        ("Acquisition", (r"\bacquisition\b", r"\bacquire(?:s|d|ment)?\b")),
        ("Disposal", (r"\bdisposal\b", r"\basset sale\b", r"\bsale of\b")),
        ("Contracts", (r"\bcontract\b", r"\border\b", r"\btender\b")),
        (
            "Results & trading",
            (
                r"\btrading update\b",
                r"\btrading statement\b",
                r"\bprofit warning\b",
                r"\bfinal results\b",
                r"\binterim results\b",
                r"\bhalf[- ]year results\b",
                r"\bfull[- ]year results\b",
                r"\bannual results\b",
                r"\bguidance\b",
            ),
        ),
        (
            "Operations",
            (
                r"\boperational update\b",
                r"\bproduction update\b",
                r"\bresource update\b",
                r"\bdrilling\b",
                r"\bclinical trial\b",
                r"\bregulatory approval\b",
                r"\bfda\b",
            ),
        ),
        ("Holdings", (r"\bholding", r"\btr-?1\b", r"\bmajor holding\b")),
        (
            "Director dealing",
            (r"\bdirector dealing\b", r"\bpdmr\b", r"\bnotification of transaction"),
        ),
        (
            "Share capital",
            (
                r"\bvoting rights\b",
                r"\bissue of equity\b",
                r"\bblock listing\b",
                r"\btransaction in own shares\b",
                r"\bshare buyback\b",
            ),
        ),
        ("Remuneration", (r"\boption\b", r"\baward\b", r"\bincentive plan\b", r"\bremuneration\b")),
        ("Board & advisers", (r"\bdirectorate\b", r"\bboard\b", r"\badviser\b", r"\bceo\b", r"\bcfo\b")),
        ("Partnerships", (r"\bpartnership\b", r"\bcollaboration\b", r"\bjoint venture\b")),
        ("Listing status", (r"\bsuspension\b", r"\brestoration\b", r"\blisting status\b")),
        (
            "Corporate",
            (
                r"\bagm\b",
                r"\bannual report\b",
                r"\bgeneral meeting\b",
                r"\bstrategic review\b",
                r"\bcapital return\b",
            ),
        ),
    ]
    for label, patterns in rules:
        if _matches(patterns, text):
            return label
    return "Other"


def canonical_rns_type(announcement: AnnouncementLike, proposed: object = "") -> str:
    """Normalise model output to the public taxonomy without inventing a category."""

    # Distress is high-stakes and should never be hidden behind a generic label or
    # ordinary fundraising category when the evidence supports solvency framing.
    if _matches(SOLVENCY_PATTERNS, _announcement_text(announcement)):
        return "Funding & solvency"

    aliases = {
        "funding and solvency": "Funding & solvency",
        "funding & solvency": "Funding & solvency",
        "solvency": "Funding & solvency",
        "insolvency": "Funding & solvency",
        "going concern": "Funding & solvency",
        "results and trading": "Results & trading",
        "results & trading": "Results & trading",
        "contracts and orders": "Contracts",
        "contract": "Contracts",
        "m&a acquisition": "Acquisition",
        "m&a disposal": "Disposal",
        "possible offer": "Takeover",
        "takeovers": "Takeover",
        "director dealings": "Director dealing",
        "board and advisers": "Board & advisers",
        "board & advisers": "Board & advisers",
        "shareholder holdings": "Holdings",
        "operational": "Operations",
    }
    canonical_by_lower = {label.lower(): label for label in CANONICAL_RNS_TYPES}
    clean = " ".join(str(proposed or "").strip().split())
    lower = clean.lower()
    if lower in canonical_by_lower:
        return canonical_by_lower[lower]
    if lower in aliases:
        return aliases[lower]
    if lower and lower not in {"other", "unknown", "uncategorised", "unclassified"}:
        # Do not silently expose an arbitrary model-created taxonomy. Prefer a
        # deterministic supported category when available; otherwise retain Other.
        inferred = classify_metadata_type(announcement)
        return inferred if inferred != "Other" else "Other"
    return classify_metadata_type(announcement)
