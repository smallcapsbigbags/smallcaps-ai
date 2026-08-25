from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from analyst.classification import classify_metadata_type, is_administrative_routine

ProcessingLevel = Literal["archive", "light", "full"]
TriageStatus = Literal["recorded", "complete", "queued", "retryable"]

TRIAGE_VERSION = "newsroom-triage-1.1"


class TriageAnnouncementLike(Protocol):
    source_id: str
    ticker: str
    company: str
    published_at: object
    title: str
    source_url: str
    categories: list[str]


@dataclass(frozen=True)
class TriageContext:
    recent_director_dealings: int = 0
    recent_adverse_trading: bool = False
    latest_revenue_value: str = ""
    latest_share_count_value: str = ""


@dataclass(frozen=True)
class TriageDecision:
    triage_class: ProcessingLevel
    processing_level: ProcessingLevel
    reason: str
    priority: int
    escalated: bool = False
    escalation_reason: str = ""
    light_facts: list[dict[str, str]] = field(default_factory=list)


_FULL_METADATA_PATTERNS: tuple[str, ...] = (
    r"\btrading (?:update|statement)\b",
    r"\bprofit warning\b",
    r"\b(?:final|interim|half[- ]year|full[- ]year|annual) results\b",
    r"\b(?:guidance|outlook) (?:update|change|revision|upgrade|downgrade)\b",
    r"\b(?:placing|fundrais(?:e|ing)|retail offer|open offer)\b",
    r"\b(?:acquisition|disposal|strategic review)\b",
    r"\b(?:possible offer|firm offer|takeover|scheme of arrangement)\b",
    r"\b(?:administration|administrators?|insolvency|liquidation|going concern)\b",
    r"\b(?:funding|financing|working capital|covenant) (?:update|shortfall|breach)\b",
    r"\b(?:clinical trial|regulatory approval|fda approval|production start|first production)\b",
    r"\b(?:suspension|restoration) of trading\b",
)

_LIGHT_METADATA_PATTERNS: tuple[str, ...] = (
    r"\bcontract(?: win| award| extension)?\b",
    r"\border(?: win| award)?\b",
    r"\bdirector(?:ate)?\b",
    r"\b(?:ceo|cfo|chief executive|chief financial officer)\b",
    r"\bpdmr\b",
    r"\bnotification of transaction\b",
    r"\bholding(?:s|\(s\))? in company\b",
    r"\btr-?1\b",
    r"\bmajor holding\b",
    r"\b(?:ltip|long[- ]term incentive|remuneration|award of options?|grant of awards?)\b",
    r"\b(?:operational|production|resource|drilling) update\b",
    r"\b(?:partnership|collaboration|joint venture)\b",
)

_EVIDENCE_ESCALATION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bprofit warning\b", "explicit profit warning"),
    (r"\b(?:guidance|expectations?)\b.{0,80}\b(?:cut|lowered|reduced|downgraded|withdrawn|below)\b", "guidance deterioration"),
    (r"\b(?:upgrade|raised|ahead of expectations|materially ahead)\b", "material guidance improvement"),
    (r"\b(?:insolvent|insolvency|administration|administrators?|liquidation)\b", "solvency event"),
    (r"\b(?:material uncertainty|insufficient funds?|funding shortfall|working capital shortfall)\b", "funding or going-concern risk"),
    (r"\b(?:placing|fundraising|retail offer|open offer)\b", "equity funding event"),
    (r"\b(?:acquisition|disposal|possible offer|firm offer|takeover|strategic review)\b", "corporate transaction"),
    (r"\b(?:material|transformational) contract\b", "contract described as material"),
    (r"\bcontract\b.{0,100}\b(?:material|transformational)\b", "contract described as material"),
    (r"\b(?:ceo|cfo|chief executive|chief financial officer)\b.{0,100}\b(?:resign|resigned|resignation|depart|departure|leave|leaving)\b", "senior executive departure"),
    (r"\b(?:resign|resigned|resignation|depart|departure|leave|leaving)\b.{0,100}\b(?:ceo|cfo|chief executive|chief financial officer)\b", "senior executive departure"),
)

_MONEY_RE = re.compile(
    r"(?:£|GBP\s*)(\d[\d,]*(?:\.\d+)?)\s*(bn|billion|m|million|k|thousand)?",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")
_ROLE_RE = re.compile(
    r"\b(CEO|CFO|Chief Executive(?: Officer)?|Chief Financial Officer|PDMR)\b",
    re.IGNORECASE,
)
_SECURITY_COUNT_RE = re.compile(
    r"\b(\d+(?:[,.]\d+)*)\s*(bn|billion|m|million|k|thousand)?\s+"
    r"(?:(?:nil[- ]cost|performance|restricted)\s+)?"
    r"(?:ordinary\s+)?(?:shares?|options?|awards?)\b",
    re.IGNORECASE,
)


def _metadata_text(item: TriageAnnouncementLike) -> str:
    return " ".join([item.title, *getattr(item, "categories", [])])


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(
        re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        for pattern in patterns
    )


def triage_metadata(item: TriageAnnouncementLike) -> TriageDecision:
    """Classify catalogue metadata before any expensive evidence/model work.

    Unknown items deliberately default to LIGHT, not ARCHIVE. The funnel saves
    compute by proving routine-ness rather than assuming it.
    """

    text = _metadata_text(item)
    if is_administrative_routine(item):
        return TriageDecision(
            triage_class="archive",
            processing_level="archive",
            reason="Deterministic administrative disclosure; retained for completeness.",
            priority=5,
        )
    if _matches(_FULL_METADATA_PATTERNS, text):
        return TriageDecision(
            triage_class="full",
            processing_level="full",
            reason="Catalogue metadata identifies a potentially investment-case-changing event.",
            priority=90,
        )
    if _matches(_LIGHT_METADATA_PATTERNS, text):
        return TriageDecision(
            triage_class="light",
            processing_level="light",
            reason="Potentially useful event requires evidence screening before deep analysis.",
            priority=55,
        )
    return TriageDecision(
        triage_class="light",
        processing_level="light",
        reason="Uncertain catalogue metadata defaults to LIGHT so material events are not silently archived.",
        priority=45,
    )


def extract_light_facts(text: str, *, limit: int = 12) -> list[dict[str, str]]:
    """Extract a tiny deterministic evidence sketch for later reprocessing/audit."""

    facts: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        key = (kind, value.lower())
        if value and key not in seen and len(facts) < limit:
            seen.add(key)
            facts.append({"kind": kind, "value": value})

    for match in _MONEY_RE.finditer(text):
        add("money", match.group(0).strip())
    for match in _PERCENT_RE.finditer(text):
        add("percent", match.group(0).strip())
    for match in _ROLE_RE.finditer(text):
        add("role", match.group(0).strip())
    for match in _SECURITY_COUNT_RE.finditer(text):
        add("securities", match.group(0).strip())
    return facts


def _scaled_number(number: str, suffix: str | None) -> float:
    value = float(number.replace(",", ""))
    multiplier = {
        "bn": 1_000_000_000,
        "billion": 1_000_000_000,
        "m": 1_000_000,
        "million": 1_000_000,
        "k": 1_000,
        "thousand": 1_000,
    }.get((suffix or "").lower(), 1.0)
    return value * multiplier


def _money_to_gbp(number: str, suffix: str | None) -> float:
    return _scaled_number(number, suffix)


def parse_numeric_amount(value: object) -> float:
    text = str(value or "").replace(",", "").strip()
    match = re.search(
        r"(?:£|GBP\s*)?\s*(\d+(?:\.\d+)?)\s*(bn|billion|m|million|k|thousand)?",
        text,
        re.IGNORECASE,
    )
    return _scaled_number(match.group(1), match.group(2)) if match else 0.0


def _largest_security_count(text: str) -> float:
    return max(
        (_scaled_number(match.group(1), match.group(2)) for match in _SECURITY_COUNT_RE.finditer(text)),
        default=0.0,
    )


def triage_evidence(
    item: TriageAnnouncementLike,
    text: str,
    *,
    context: TriageContext | None = None,
) -> TriageDecision:
    """Escalate LIGHT items using exact evidence and narrow Company Memory context.

    No analyst LLM is used. Missing denominators are treated conservatively: large
    absolute events escalate rather than being incorrectly suppressed.
    """

    context = context or TriageContext()
    light_facts = extract_light_facts(text)
    for pattern, reason in _EVIDENCE_ESCALATION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a full-analysis trigger.",
                priority=95 if reason in {"solvency event", "funding or going-concern risk"} else 88,
                escalated=True,
                escalation_reason=reason,
                light_facts=light_facts,
            )

    metadata = _metadata_text(item)
    if re.search(r"\b(?:contract|order|tender)\b", metadata, flags=re.IGNORECASE):
        amounts = [
            _money_to_gbp(match.group(1), match.group(2))
            for match in _MONEY_RE.finditer(text)
        ]
        contract_value = max(amounts, default=0.0)
        revenue = parse_numeric_amount(context.latest_revenue_value)
        if contract_value and revenue and contract_value / revenue >= 0.10:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a company-scale material contract/order.",
                priority=85,
                escalated=True,
                escalation_reason="contract/order value is at least 10% of latest known revenue",
                light_facts=light_facts,
            )
        if contract_value >= 5_000_000 and not revenue:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a large contract with no reliable revenue denominator.",
                priority=80,
                escalated=True,
                escalation_reason="contract/order value is at least £5m and latest revenue is unavailable",
                light_facts=light_facts,
            )
        # Keep the existing conservative absolute backstop even when revenue is known.
        if contract_value >= 2_000_000:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a sizeable disclosed contract value.",
                priority=82,
                escalated=True,
                escalation_reason="contract value of at least £2m requires full materiality analysis",
                light_facts=light_facts,
            )

    if re.search(
        r"\b(?:ltip|long[- ]term incentive|grant of awards?|option)\b",
        metadata,
        flags=re.IGNORECASE,
    ):
        percentages = [float(match.group(1)) for match in _PERCENT_RE.finditer(text)]
        if percentages and max(percentages) >= 3.0:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found potentially material dilution.",
                priority=82,
                escalated=True,
                escalation_reason="award/options disclosure includes at least 3%",
                light_facts=light_facts,
            )
        award_count = _largest_security_count(text)
        share_count = parse_numeric_amount(context.latest_share_count_value)
        if award_count and share_count and award_count / share_count >= 0.03:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found potentially material dilution versus stored share count.",
                priority=82,
                escalated=True,
                escalation_reason="award/options count is at least 3% of latest known share count",
                light_facts=light_facts,
            )
        if award_count >= 2_000_000 and not share_count:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a large award count without a reliable share-count denominator.",
                priority=72,
                escalated=True,
                escalation_reason="award/options count is at least 2m and latest share count is unavailable",
                light_facts=light_facts,
            )

    if re.search(
        r"\b(?:director dealing|pdmr|notification of transaction)\b",
        metadata,
        flags=re.IGNORECASE,
    ):
        roles = [match.group(0).lower() for match in _ROLE_RE.finditer(text)]
        amounts = [
            _money_to_gbp(match.group(1), match.group(2))
            for match in _MONEY_RE.finditer(text)
        ]
        senior = any(
            role
            in {
                "ceo",
                "cfo",
                "chief executive",
                "chief executive officer",
                "chief financial officer",
            }
            for role in roles
        )
        if senior:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a CEO/CFO transaction.",
                priority=78,
                escalated=True,
                escalation_reason="CEO/CFO director dealing requires full context",
                light_facts=light_facts,
            )
        if amounts and max(amounts) >= 100_000:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a large director transaction.",
                priority=76,
                escalated=True,
                escalation_reason="director transaction value is at least £100k",
                light_facts=light_facts,
            )
        if context.recent_director_dealings >= 2:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a repeated director-dealing pattern.",
                priority=74,
                escalated=True,
                escalation_reason="at least two recent director dealings are already stored",
                light_facts=light_facts,
            )
        if context.recent_adverse_trading:
            return TriageDecision(
                triage_class="light",
                processing_level="full",
                reason="LIGHT evidence screening found a director event after adverse trading.",
                priority=80,
                escalated=True,
                escalation_reason="director dealing follows a recent adverse trading disclosure",
                light_facts=light_facts,
            )

    return TriageDecision(
        triage_class="light",
        processing_level="light",
        reason="Evidence screen found no deterministic trigger for full Analyst 3.3 processing.",
        priority=50,
        light_facts=light_facts,
    )


def catalogue_hash(item: TriageAnnouncementLike) -> str:
    payload = "\x1f".join(
        [
            item.source_id,
            item.ticker,
            item.company,
            str(item.published_at),
            item.title,
            item.source_url,
            *getattr(item, "categories", []),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def evidence_hash(text: str, source_urls: list[str]) -> str:
    payload = "\x1f".join([text, *source_urls])
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def triage_rns_type(item: TriageAnnouncementLike) -> str:
    return classify_metadata_type(item)
