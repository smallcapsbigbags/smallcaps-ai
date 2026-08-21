from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol


class AnnouncementLike(Protocol):
    title: str
    categories: list[str]


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
    r"\bholding(?:s)? in company\b",
    r"\bmajor holding\b",
    r"\bnotification of major holdings\b",
    r"\bdirector dealing\b",
    r"\bpdmr\b",
    r"\bnotification of transactions?\b",
    r"\btransaction by (?:a )?(?:director|pdmr)\b",
]

MATERIAL_PATTERNS = [
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
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _announcement_text(announcement: AnnouncementLike) -> str:
    return " ".join([announcement.title, *announcement.categories])


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
    if _matches(MATERIAL_PATTERNS, text):
        return 90
    if _matches(OWNERSHIP_PATTERNS, text):
        return 62
    if not is_administrative_routine(announcement):
        return 38
    return 5


def classify_metadata_type(announcement: AnnouncementLike) -> str:
    text = _announcement_text(announcement).lower()
    rules = [
        ("Holdings", ("holding", "tr-1")),
        (
            "Director dealing",
            ("director dealing", "pdmr", "notification of transaction"),
        ),
        (
            "Share capital",
            (
                "voting rights",
                "issue of equity",
                "block listing",
                "transaction in own shares",
            ),
        ),
        ("Remuneration", ("option", "award", "incentive plan", "remuneration")),
        ("Contracts", ("contract", "order", "tender")),
        ("Fundraising", ("placing", "fundrais", "subscription", "retail offer")),
        (
            "Results & trading",
            ("results", "trading update", "trading statement", "profit warning", "guidance"),
        ),
        ("Board & advisers", ("directorate", "board", "adviser", "ceo", "cfo")),
        ("Partnerships", ("partnership", "collaboration", "joint venture")),
        ("Listing status", ("suspension", "restoration", "listing status")),
        (
            "Corporate",
            ("agm", "annual report", "general meeting", "scheme of arrangement"),
        ),
    ]
    for label, needles in rules:
        if any(needle in text for needle in needles):
            return label
    return "Other"
