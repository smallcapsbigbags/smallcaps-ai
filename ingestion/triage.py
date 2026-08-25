from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from analyst.models import AnnouncementInput
from ingestion.investegate_daily import CatalogueAnnouncement

ProcessingLevel = Literal["ARCHIVE", "LIGHT", "FULL"]
TRIAGE_VERSION = "newsroom-triage-1.0"


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
    score: int
    escalated: bool = False
    escalation_reason: str = ""
    light_facts: list[dict[str, object]] = field(default_factory=list)


_ARCHIVE_PATTERNS = (
    r"\btotal voting rights\b",
    r"\bblock listing(?: six monthly return| interim review)?\b",
    r"\bnotice of agm\b",
    r"\bresults? of agm\b",
    r"\bpublication of annual report\b",
    r"\bannual report and accounts\b",
    r"\bchange of registered office\b",
    r"\bnotice of results\b",
)

_FULL_PATTERNS = (
    r"\btrading update\b",
    r"\btrading statement\b",
    r"\bprofit warning\b",
    r"\bguidance (?:update|change|revision)\b",
    r"\bfinal results\b",
    r"\binterim results\b",
    r"\bhalf[- ]year results\b",
    r"\bfull[- ]year results\b",
    r"\bannual results\b",
    r"\bplacing\b",
    r"\bfundrais(?:e|ing)\b",
    r"\bsubscription and placing\b",
    r"\bretail offer\b",
    r"\bopen offer\b",
    r"\bacquisition\b",
    r"\bdisposal\b",
    r"\bstrategic review\b",
    r"\bpossible offer\b",
    r"\bfirm offer\b",
    r"\btakeover\b",
    r"\bscheme of arrangement\b",
    r"\bfunding update\b",
    r"\bfinancing update\b",
    r"\bworking capital update\b",
    r"\brefinanc\w*\b",
    r"\bcovenant\b",
    r"\badministrat(?:ion|or)\b",
    r"\binsolven\w*\b",
    r"\bgoing concern\b",
    r"\bclinical trial results?\b",
    r"\bregulatory approval\b",
    r"\bproduction update\b",
    r"\bresource update\b",
    r"\bshare buyback programme\b",
    r"\bcapital return\b",
)

_LIGHT_PATTERNS = (
    r"\bdirector(?:/pdmr)? shareholding\b",
    r"\bdirector dealing\b",
    r"\bpdmr\b",
    r"\bholding(?:\(s\)|s)? in company\b",
    r"\bmajor holding\b",
    r"\btr-?1\b",
    r"\blong[- ]term incentive\b",
    r"\bltip\b",
    r"\bgrant of (?:awards?|options?)\b",
    r"\bremuneration\b",
    r"\bdirectorate change\b",
    r"\bboard change\b",
    r"\bappointment of director\b",
    r"\bchange of adviser\b",
    r"\bcontract(?: win| award)?\b",
    r"\border(?: win| award)?\b",
    r"\btender\b",
    r"\bpartnership\b",
    r"\bcollaboration\b",
    r"\bjoint venture\b",
    r"\bissue of equity\b",
    r"\btransaction in own shares\b",
)

_HIGH_RISK_EVIDENCE_PATTERNS = (
    r"\bprofit warning\b",
    r"\b(?:materially|significantly) below (?:market |current )?expectations\b",
    r"\bguidance (?:has been |is )?(?:cut|lowered|reduced|withdrawn|suspended)\b",
    r"\bgoing concern\b.{0,140}\b(?:material uncertainty|insufficient|unable)\b",
    r"\b(?:material uncertainty|insufficient funds?|unable)\b.{0,140}\bgoing concern\b",
    r"\bnotice of intention to appoint administrators?\b",
    r"\badministrators? (?:have been |has been )?appointed\b",
    r"\binsolven\w*\b",
    r"\bcovenant\w*\b.{0,120}\b(?:breach|waiver|non[- ]compliance)\b",
    r"\b(?:placing|fundraising|fundraise|rescue financing|emergency funding)\b",
    r"\bpossible offer\b",
    r"\bfirm offer\b",
    r"\bstrategic review\b",
)

_MONEY_RE = re.compile(
    r"(?P<currency>£|GBP\s*)\s*(?P<number>\d+(?:[,.]\d+)*)\s*"
    r"(?P<scale>bn|billion|m|million|k|thousand)?",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")
_SECURITY_COUNT_RE = re.compile(
    r"\b(\d+(?:[,.]\d+)*)\s*(bn|billion|m|million|k|thousand)?\s+"
    r"(?:ordinary\s+)?(?:shares?|options?|awards?)\b",
    re.IGNORECASE,
)


def _text(item: object) -> str:
    title = str(getattr(item, "title", "") or "")
    categories = getattr(item, "categories", []) or []
    return " ".join([title, *[str(value) for value in categories]])


def _matches(patterns: tuple[str, ...], text: str) -> bool:
    return any(
        re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        for pattern in patterns
    )


def initial_triage(item: CatalogueAnnouncement) -> TriageDecision:
    """Classify catalogue metadata before any evidence/model call.

    Unknown items default to LIGHT rather than ARCHIVE. That is intentionally
    conservative: low confidence costs one evidence retrieval, while an incorrect
    archive decision could hide a material event.
    """

    text = _text(item)
    if _matches(_FULL_PATTERNS, text):
        return TriageDecision(
            "FULL",
            "FULL",
            "High-signal event class in catalogue metadata.",
            90,
        )
    if _matches(_ARCHIVE_PATTERNS, text):
        return TriageDecision(
            "ARCHIVE",
            "ARCHIVE",
            "Routine administrative disclosure identified deterministically.",
            5,
        )
    if _matches(_LIGHT_PATTERNS, text):
        return TriageDecision(
            "LIGHT",
            "LIGHT",
            "Potentially useful event requires a lightweight evidence screen.",
            45,
        )
    return TriageDecision(
        "LIGHT",
        "LIGHT",
        "Unclassified catalogue item fails safe to lightweight evidence screening.",
        50,
    )


def assess_light(
    announcement: AnnouncementInput,
    *,
    context: TriageContext | None = None,
    initial: TriageDecision | None = None,
) -> TriageDecision:
    """Decide whether a LIGHT item must escalate to full Analyst 3.3.

    No LLM is used here. The screen combines exact retrieved evidence with stored
    company context, so model spend is reserved for items that cross explicit risk,
    scale or governance thresholds.
    """

    context = context or TriageContext()
    initial = initial or TriageDecision(
        "LIGHT", "LIGHT", "Light evidence screen.", 45
    )
    text = " ".join(
        [announcement.title, announcement.text, *announcement.categories]
    )
    facts = extract_light_facts(announcement.text)
    reasons: list[str] = []
    score = initial.score

    if _matches(_HIGH_RISK_EVIDENCE_PATTERNS, text):
        reasons.append(
            "Retrieved evidence contains a high-risk investment-case trigger."
        )
        score = max(score, 95)

    lower = text.lower()
    is_director = bool(re.search(r"\b(?:director|pdmr)\b", lower))
    if is_director:
        if re.search(
            r"\b(?:chief executive|chief financial officer|ceo|cfo)\b", lower
        ):
            reasons.append("CEO/CFO dealing or change warrants full context.")
            score = max(score, 78)
        if context.recent_director_dealings >= 2:
            reasons.append(
                "Repeated director-dealing pattern detected in recent company history."
            )
            score = max(score, 72)
        if context.recent_adverse_trading:
            reasons.append("Director event follows a recent adverse trading disclosure.")
            score = max(score, 80)
        if _largest_money(text) >= 100_000:
            reasons.append("Director transaction value is at least £100k.")
            score = max(score, 75)

    is_contract = bool(re.search(r"\b(?:contract|order|tender)\b", lower))
    if is_contract:
        contract_value = _largest_money(text)
        revenue = parse_numeric_amount(context.latest_revenue_value)
        if contract_value and revenue and contract_value / revenue >= 0.10:
            reasons.append(
                "Disclosed contract/order value is at least 10% of latest known revenue."
            )
            score = max(score, 85)
        elif contract_value >= 5_000_000 and not revenue:
            reasons.append(
                "Contract/order value is at least £5m and no reliable revenue denominator is stored."
            )
            score = max(score, 78)
        if re.search(
            r"\b(?:largest|transformational|material to the group)\b", lower
        ):
            reasons.append(
                "Company describes the commercial event as unusually material."
            )
            score = max(score, 80)

    is_ltip = bool(
        re.search(r"\b(?:ltip|incentive|options?|awards?)\b", lower)
    )
    if is_ltip:
        award_shares = _largest_security_count(text)
        total_shares = parse_numeric_amount(context.latest_share_count_value)
        if award_shares and total_shares and award_shares / total_shares >= 0.03:
            reasons.append(
                "Award/options represent at least 3% of latest known share count."
            )
            score = max(score, 82)
        elif award_shares >= 2_000_000 and not total_shares:
            reasons.append(
                "Large option/award count with no reliable share-count denominator stored."
            )
            score = max(score, 70)

    if re.search(
        r"\b(?:resign|resignation|steps? down|leaves? the company)\b", lower
    ) and re.search(
        r"\b(?:chief executive|chief financial officer|ceo|cfo)\b", lower
    ):
        reasons.append("CEO/CFO departure is potentially investment-case relevant.")
        score = max(score, 88)

    if reasons:
        return TriageDecision(
            triage_class=initial.triage_class,
            processing_level="FULL",
            reason=initial.reason,
            score=score,
            escalated=True,
            escalation_reason=" ".join(dict.fromkeys(reasons)),
            light_facts=facts,
        )

    return TriageDecision(
        triage_class=initial.triage_class,
        processing_level="LIGHT",
        reason=initial.reason,
        score=score,
        light_facts=facts,
    )


def extract_light_facts(text: str) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = []
    for match in _MONEY_RE.finditer(text):
        raw = match.group(0).strip()
        facts.append(
            {
                "kind": "money",
                "value": raw,
                "value_numeric": parse_numeric_amount(raw),
            }
        )
    for match in _PERCENT_RE.finditer(text):
        facts.append(
            {
                "kind": "percentage",
                "value": match.group(0),
                "value_numeric": float(match.group(1)),
            }
        )
    for match in _SECURITY_COUNT_RE.finditer(text):
        raw = match.group(0).strip()
        facts.append(
            {
                "kind": "securities",
                "value": raw,
                "value_numeric": parse_numeric_amount(raw),
            }
        )
    return facts[:12]


def parse_numeric_amount(value: object) -> float:
    text = str(value or "").replace(",", "").strip()
    match = re.search(
        r"(?:£|GBP\s*)?\s*(\d+(?:\.\d+)?)\s*"
        r"(bn|billion|m|million|k|thousand)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return 0.0
    number = float(match.group(1))
    scale = (match.group(2) or "").lower()
    factor = {
        "bn": 1_000_000_000,
        "billion": 1_000_000_000,
        "m": 1_000_000,
        "million": 1_000_000,
        "k": 1_000,
        "thousand": 1_000,
    }.get(scale, 1)
    return number * factor


def _largest_money(text: str) -> float:
    return max(
        (parse_numeric_amount(match.group(0)) for match in _MONEY_RE.finditer(text)),
        default=0.0,
    )


def _largest_security_count(text: str) -> float:
    return max(
        (
            parse_numeric_amount(match.group(0))
            for match in _SECURITY_COUNT_RE.finditer(text)
        ),
        default=0.0,
    )
