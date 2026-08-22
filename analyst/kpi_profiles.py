from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from analyst.models import AnnouncementInput, StrictModel

KPIRole = Literal["primary", "quality", "balance-sheet", "risk", "delivery"]


class KPIPriority(StrictModel):
    metric: str
    role: KPIRole
    why: str
    aliases: list[str] = Field(default_factory=list)


class KPIProfileSnapshot(StrictModel):
    """A deterministic company-archetype checklist, not a company fact."""

    context_type: Literal["sector_kpi_profile"] = "sector_kpi_profile"
    profile_id: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    score: int = Field(ge=0)
    matched_signals: list[str] = Field(default_factory=list)
    priority_kpis: list[KPIPriority] = Field(default_factory=list)
    relationship_checks: list[str] = Field(default_factory=list)
    sector_questions: list[str] = Field(default_factory=list)

    def to_context_record(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload["profile_rules"] = [
            "This is a deterministic analytical checklist inferred from supplied evidence, not a company-reported sector classification.",
            "Use a priority KPI only when the current announcement or eligible history actually discloses it.",
            "Do not invent a missing metric, denominator, comparator or valuation input.",
            "A low-confidence or generic profile must not override the main economic change in today's RNS.",
        ]
        return payload


@dataclass(frozen=True)
class _ProfileTemplate:
    profile_id: str
    label: str
    signals: tuple[tuple[str, int], ...]
    priorities: tuple[tuple[str, KPIRole, str, tuple[str, ...]], ...]
    relationship_checks: tuple[str, ...]
    sector_questions: tuple[str, ...]


_GENERIC = _ProfileTemplate(
    profile_id="generic",
    label="General small-cap company",
    signals=(),
    priorities=(
        ("Revenue", "primary", "Shows the scale and direction of trading.", ("revenue", "sales")),
        ("Profit / EBITDA", "quality", "Tests whether growth converts into earnings.", ("profit", "ebitda", "operating profit", "pbt")),
        ("Margin", "quality", "Shows whether revenue quality is improving or deteriorating.", ("margin", "gross margin", "operating margin", "ebitda margin")),
        ("Cash / net debt", "balance-sheet", "Shows funding risk and financial flexibility.", ("cash", "net cash", "net debt", "liquidity")),
        ("Guidance", "delivery", "Provides the strongest company-set comparator for today's result.", ("guidance", "outlook", "expectations")),
    ),
    relationship_checks=(
        "Revenue growth versus profit and margin movement",
        "Profit movement versus cash conversion and net debt",
        "Today's result versus the latest explicit company guidance",
    ),
    sector_questions=(
        "What changed versus the latest company guidance or prior disclosure?",
        "Is growth organic, acquired, price-led, volume-led or temporary?",
        "What does the update do to cash, debt, dilution and funding risk?",
    ),
)


_PROFILES: tuple[_ProfileTemplate, ...] = (
    _ProfileTemplate(
        profile_id="housebuilder",
        label="Housebuilder",
        signals=(
            ("housebuilder", 8),
            ("housing completions", 7),
            ("private completions", 7),
            ("affordable housing", 6),
            ("average selling price", 6),
            ("land bank", 6),
            ("plots", 4),
            ("reservations", 5),
            ("sales outlets", 5),
            ("planning consent", 4),
            ("homes sold", 5),
        ),
        priorities=(
            ("Completions / reservations", "primary", "Measures current sales volume and forward demand.", ("completions", "reservations", "homes sold")),
            ("Average selling price", "primary", "Separates volume from pricing and mix.", ("average selling price", "asp")),
            ("Gross / operating margin", "quality", "Tests whether sales growth creates value after build-cost and incentive pressure.", ("gross margin", "operating margin", "margin")),
            ("Net debt / net cash", "balance-sheet", "Captures working-capital and land-investment risk.", ("net debt", "net cash", "cash")),
            ("Land bank / order book", "delivery", "Shows the pipeline available for future completions.", ("land bank", "plots", "order book")),
        ),
        relationship_checks=(
            "Completions and selling prices versus margin",
            "Land investment and working capital versus net debt",
            "Reservations and order book versus future completion guidance",
        ),
        sector_questions=(
            "Is volume growth being bought through incentives or weaker margin?",
            "Does the company have surplus cash after land and working-capital needs?",
            "Are reservations, outlets and land availability sufficient for guidance?",
        ),
    ),
    _ProfileTemplate(
        profile_id="property",
        label="Property company / REIT",
        signals=(
            ("reit", 8),
            ("epra nta", 8),
            ("epra nav", 8),
            ("loan to value", 7),
            ("ltv", 6),
            ("occupancy", 6),
            ("rent collection", 6),
            ("property portfolio", 6),
            ("annualised rent", 5),
            ("book value", 4),
            ("valuation yield", 5),
            ("void rate", 5),
        ),
        priorities=(
            ("EPRA NTA / NAV", "primary", "Measures the property value attributable to shareholders.", ("epra nta", "epra nav", "nav", "nta")),
            ("Rental income / occupancy", "quality", "Tests the operating quality of the portfolio.", ("rental income", "occupancy", "rent collection")),
            ("LTV / net debt", "balance-sheet", "Shows refinancing and covenant risk.", ("ltv", "loan to value", "net debt")),
            ("Disposal price versus book value", "delivery", "Shows whether stated asset values are being realised in cash.", ("disposal", "sale proceeds", "book value")),
            ("Dividend / capital return capacity", "delivery", "Links cash realisation to shareholder returns.", ("dividend", "capital return", "distribution")),
        ),
        relationship_checks=(
            "Asset-sale proceeds versus book value and debt reduction",
            "NAV movement versus occupancy, rents and valuation yield",
            "LTV and interest cost versus refinancing headroom",
        ),
        sector_questions=(
            "Are disposals validating or undermining reported asset values?",
            "Will planned sales actually repay debt and support capital returns?",
            "How exposed is the equity to refinancing, vacancies and yield expansion?",
        ),
    ),
    _ProfileTemplate(
        profile_id="recruiter",
        label="Recruitment company",
        signals=(
            ("net fee income", 9),
            ("nfi", 8),
            ("contractor billings", 7),
            ("permanent fees", 6),
            ("sales headcount", 7),
            ("recruitment", 7),
            ("placements", 5),
            ("contractor book", 6),
        ),
        priorities=(
            ("Net fee income", "primary", "Removes contractor payroll pass-through and shows the economically meaningful top line.", ("net fee income", "nfi")),
            ("Underlying profit / conversion", "quality", "Shows operating leverage from fee income into profit.", ("underlying pbt", "underlying profit", "conversion", "operating profit")),
            ("Sales headcount / productivity", "delivery", "Tests whether margin gains come from sustainable productivity or temporary cost cuts.", ("sales headcount", "headcount", "productivity")),
            ("Permanent versus contract mix", "risk", "Shows exposure to cyclical hiring conditions and revenue quality.", ("permanent fees", "contract nfi", "contractor book")),
            ("Net cash", "balance-sheet", "Shows resilience through a recruitment downturn.", ("net cash", "cash", "net debt")),
        ),
        relationship_checks=(
            "Net fee income growth versus underlying profit growth",
            "Margin or conversion versus sales headcount",
            "Permanent and contract fee trends versus the economic cycle",
        ),
        sector_questions=(
            "Is reported revenue mostly contractor payroll pass-through?",
            "Did profit improve because of genuine fee growth or lower headcount?",
            "Can operating leverage persist if recruitment and investment resume?",
        ),
    ),
    _ProfileTemplate(
        profile_id="software",
        label="Software / SaaS company",
        signals=(
            ("annual recurring revenue", 9),
            ("arr", 8),
            ("saas", 8),
            ("subscription revenue", 7),
            ("recurring revenue", 7),
            ("net revenue retention", 8),
            ("gross revenue retention", 7),
            ("churn", 7),
            ("licence revenue", 5),
            ("monthly recurring revenue", 8),
        ),
        priorities=(
            ("ARR / recurring revenue", "primary", "Shows the repeatable revenue base rather than one-off implementation work.", ("arr", "annual recurring revenue", "recurring revenue", "mrr")),
            ("Retention / churn", "quality", "Tests whether recurring revenue is durable.", ("retention", "churn", "nrr", "grr")),
            ("Gross margin", "quality", "Shows the economics of software and service delivery.", ("gross margin", "contribution margin")),
            ("Free cash flow / cash burn", "balance-sheet", "Shows whether growth is self-funded.", ("free cash flow", "cash burn", "operating cash flow", "cash")),
            ("Bookings / backlog", "delivery", "Provides evidence for future revenue conversion.", ("bookings", "backlog", "order book")),
        ),
        relationship_checks=(
            "ARR growth versus retention and churn",
            "Revenue growth versus gross margin and cash burn",
            "Bookings or backlog versus revenue recognition timing",
        ),
        sector_questions=(
            "How much growth is recurring rather than services or one-off licence revenue?",
            "Is growth efficient after sales, development and implementation costs?",
            "Does the company have enough cash runway to reach sustainable cash generation?",
        ),
    ),
    _ProfileTemplate(
        profile_id="lender",
        label="Specialist lender / financial services",
        signals=(
            ("loan book", 9),
            ("net interest margin", 8),
            ("cost of risk", 8),
            ("credit loss", 7),
            ("arrears", 7),
            ("originations", 6),
            ("capital ratio", 7),
            ("impairment", 6),
            ("lending", 5),
            ("return on equity", 6),
        ),
        priorities=(
            ("Loan book / originations", "primary", "Shows lending growth and balance-sheet deployment.", ("loan book", "originations", "new business")),
            ("Net interest margin", "quality", "Shows pricing and funding economics.", ("net interest margin", "nim", "yield")),
            ("Cost of risk / arrears", "risk", "Tests whether growth is weakening credit quality.", ("cost of risk", "arrears", "impairment", "credit loss")),
            ("Capital / liquidity", "balance-sheet", "Shows capacity to fund growth and absorb losses.", ("capital ratio", "liquidity", "funding facility", "cash")),
            ("Return on equity", "quality", "Links growth, margin and credit losses to shareholder returns.", ("return on equity", "roe", "roae")),
        ),
        relationship_checks=(
            "Loan-book growth versus arrears, impairments and cost of risk",
            "Net interest margin versus funding cost",
            "Growth versus capital and liquidity headroom",
        ),
        sector_questions=(
            "Is faster lending growth being achieved at weaker credit quality?",
            "Are funding costs or competition compressing margin?",
            "Does capital and liquidity remain adequate after planned growth?",
        ),
    ),
    _ProfileTemplate(
        profile_id="mining",
        label="Mining / mineral resources",
        signals=(
            ("mineral resource", 8),
            ("ore reserve", 8),
            ("aisc", 9),
            ("all in sustaining cost", 9),
            ("grade", 6),
            ("recovery", 6),
            ("tonnes", 5),
            ("ounces", 5),
            ("strip ratio", 7),
            ("mine production", 8),
            ("drilling results", 5),
        ),
        priorities=(
            ("Production", "primary", "Shows physical delivery against mine guidance.", ("production", "ounces", "tonnes")),
            ("Grade / recovery", "quality", "Explains the quality and efficiency of production.", ("grade", "recovery")),
            ("AISC / cash cost", "quality", "Shows the margin retained from commodity prices.", ("aisc", "cash cost", "all in sustaining cost")),
            ("Capex / net cash", "balance-sheet", "Shows whether operational progress is affordable.", ("capex", "capital expenditure", "net cash", "net debt")),
            ("Resource / reserve", "delivery", "Shows changes to mine life and development potential, but not immediate cash generation by itself.", ("resource", "reserve", "mine life")),
        ),
        relationship_checks=(
            "Production growth versus grade, recovery and AISC",
            "Resource growth versus development capex and timetable",
            "Commodity-price benefit versus realised price and cost inflation",
        ),
        sector_questions=(
            "Did production improve because of sustainable operations or temporary grade/mix?",
            "Are costs rising faster than production or realised prices?",
            "What funding and capex are required before a resource becomes cash flow?",
        ),
    ),
    _ProfileTemplate(
        profile_id="oil-gas",
        label="Oil and gas producer",
        signals=(
            ("boepd", 9),
            ("barrels of oil equivalent", 9),
            ("2p reserves", 8),
            ("lifting cost", 7),
            ("realised oil price", 7),
            ("well result", 5),
            ("drilling programme", 6),
            ("hydrocarbon", 6),
            ("production guidance", 7),
            ("decommissioning", 6),
        ),
        priorities=(
            ("Production", "primary", "Shows physical delivery and revenue capacity.", ("production", "boepd", "barrels")),
            ("Realised price / hedging", "quality", "Separates market prices from the price actually received.", ("realised price", "hedging", "oil price", "gas price")),
            ("Operating / lifting cost", "quality", "Shows field-level cash economics.", ("lifting cost", "operating cost", "unit cost")),
            ("Capex / free cash flow", "balance-sheet", "Shows whether production and reserves are self-funded.", ("capex", "free cash flow", "net debt", "net cash")),
            ("Reserves / well delivery", "delivery", "Tests replacement of produced reserves and project execution.", ("2p reserves", "reserves", "well", "drilling")),
        ),
        relationship_checks=(
            "Production versus realised price and unit cost",
            "Reserve additions versus capex and development timetable",
            "Free cash flow versus debt, hedging and decommissioning obligations",
        ),
        sector_questions=(
            "How much of the result is volume, commodity price, hedging or FX?",
            "Are unit costs and capex rising faster than production?",
            "Does the balance sheet fund committed drilling and abandonment liabilities?",
        ),
    ),
    _ProfileTemplate(
        profile_id="life-sciences",
        label="Life sciences / medical technology",
        signals=(
            ("clinical trial", 9),
            ("phase i", 8),
            ("phase ii", 8),
            ("phase iii", 8),
            ("fda", 8),
            ("mhra", 8),
            ("regulatory approval", 7),
            ("patient enrolment", 7),
            ("cash runway", 9),
            ("medical device", 6),
            ("reimbursement", 6),
            ("drug candidate", 7),
        ),
        priorities=(
            ("Clinical / regulatory milestone", "primary", "Determines technical and regulatory de-risking.", ("clinical endpoint", "trial result", "regulatory approval", "fda", "mhra")),
            ("Cash runway / funding need", "balance-sheet", "Determines whether shareholders can reach the next value milestone without rescue financing.", ("cash runway", "cash", "funding", "working capital")),
            ("Commercial revenue / installed base", "delivery", "Shows whether approval is converting into adoption and cash receipts.", ("revenue", "installed base", "orders", "reimbursement")),
            ("Cash burn / R&D spend", "risk", "Shows the cost and pace of development.", ("cash burn", "research and development", "r and d", "operating cash flow")),
            ("Next milestone and timing", "delivery", "Provides the event path investors can verify.", ("milestone", "submission", "enrolment", "readout")),
        ),
        relationship_checks=(
            "Clinical progress versus cash runway to the next milestone",
            "Revenue growth versus losses, cash burn and funding need",
            "Regulatory progress versus commercial adoption and reimbursement",
        ),
        sector_questions=(
            "Is the technical milestone financially meaningful today or only a future option?",
            "How much cash is available and what must be funded before the next milestone?",
            "Is financing binding, sufficient and non-dilutive, or merely under discussion?",
        ),
    ),
    _ProfileTemplate(
        profile_id="retailer",
        label="Retailer / consumer company",
        signals=(
            ("like for like sales", 9),
            ("lfl sales", 8),
            ("footfall", 6),
            ("gross margin", 4),
            ("inventory", 6),
            ("stock turn", 7),
            ("stores", 4),
            ("average transaction value", 6),
            ("online sales", 5),
            ("markdown", 5),
        ),
        priorities=(
            ("Like-for-like sales", "primary", "Separates underlying trading from new-space growth.", ("like for like", "lfl", "comparable sales")),
            ("Gross margin", "quality", "Tests discounting, mix and input-cost pressure.", ("gross margin", "markdown", "promotional activity")),
            ("Inventory / stock turn", "risk", "Shows demand forecasting and future markdown risk.", ("inventory", "stock", "stock turn")),
            ("Store / online mix", "delivery", "Explains channel and space-driven growth.", ("stores", "online sales", "digital sales")),
            ("Net debt / cash", "balance-sheet", "Shows resilience through seasonal working-capital swings.", ("net debt", "cash", "working capital")),
        ),
        relationship_checks=(
            "Like-for-like sales versus gross margin",
            "Sales growth versus inventory and stock turn",
            "Store expansion versus cash generation and lease/debt obligations",
        ),
        sector_questions=(
            "Is sales growth volume-led, price-led, promotional or new-space driven?",
            "Are inventories rising faster than sales?",
            "Does margin and cash support the current rate of expansion?",
        ),
    ),
    _ProfileTemplate(
        profile_id="industrial-contracting",
        label="Industrial / contractor / project services",
        signals=(
            ("order book", 7),
            ("book to bill", 8),
            ("framework agreement", 6),
            ("project margin", 7),
            ("utilisation", 6),
            ("mobilisation", 6),
            ("contract award", 5),
            ("tender pipeline", 6),
            ("working capital", 4),
            ("fleet utilisation", 6),
        ),
        priorities=(
            ("Order book / book-to-bill", "primary", "Shows contracted future demand rather than promotional pipeline language.", ("order book", "book to bill", "backlog")),
            ("Operating / project margin", "quality", "Tests contract quality and execution.", ("operating margin", "project margin", "ebitda margin")),
            ("Cash conversion / working capital", "balance-sheet", "Shows whether accounting profit is turning into cash.", ("cash conversion", "working capital", "operating cash flow")),
            ("Utilisation / volume", "delivery", "Explains operational leverage and capacity use.", ("utilisation", "volume", "fleet utilisation")),
            ("Contract economics / timing", "risk", "Separates headline contract value from annual revenue and margin.", ("contract value", "duration", "revenue recognition", "margin")),
        ),
        relationship_checks=(
            "Order-book growth versus revenue, margin and cash conversion",
            "Contract value versus duration and annual revenue recognition",
            "Utilisation gains versus maintenance capex and working capital",
        ),
        sector_questions=(
            "Is backlog converting into profitable revenue and cash?",
            "Are contract wins incremental to forecasts or already assumed?",
            "What execution, mobilisation and working-capital risks remain?",
        ),
    ),
    _ProfileTemplate(
        profile_id="professional-services",
        label="Professional services / legal / consulting",
        signals=(
            ("fee earners", 8),
            ("profit distributable to members", 9),
            ("partner drawings", 8),
            ("lock up days", 8),
            ("lock-up", 7),
            ("utilisation", 5),
            ("legal services", 7),
            ("law firm", 8),
            ("professional services", 6),
            ("consulting", 5),
        ),
        priorities=(
            ("Fee income / revenue", "primary", "Shows the economic scale of the fee-earning base.", ("fee income", "revenue", "net revenue")),
            ("Operating profit / profit per partner", "quality", "Tests productivity and the earnings quality of acquired teams.", ("operating profit", "profit distributable", "profit per partner", "pbt")),
            ("Fee earners / utilisation", "delivery", "Explains capacity, productivity and organic growth.", ("fee earners", "headcount", "utilisation")),
            ("Lock-up / cash conversion", "risk", "Shows how quickly billed work becomes cash.", ("lock up", "lock-up", "cash conversion", "debtor days")),
            ("Net debt / acquisition funding", "balance-sheet", "Tests whether acquisition-led growth is affordable.", ("net debt", "acquisition funding", "consideration", "cash")),
        ),
        relationship_checks=(
            "Fee-income growth versus profit, fee-earner growth and utilisation",
            "Profit growth versus lock-up and cash conversion",
            "Acquisition contribution versus organic growth and net debt",
        ),
        sector_questions=(
            "Is growth organic or acquisition-led?",
            "Is the disclosed target profit comparable with normal corporate EBITDA or operating profit?",
            "Are fee growth and accounting profit converting into cash?",
        ),
    ),
)


def _normalise(value: object) -> str:
    text = " ".join(str(value or "").lower().replace("&", " and ").split())
    output = []
    for char in text:
        output.append(char if char.isalnum() else " ")
    return " ".join("".join(output).split())


def _contains(text: str, term: str) -> bool:
    clean_text = f" {_normalise(text)} "
    clean_term = _normalise(term)
    return bool(clean_term) and f" {clean_term} " in clean_text


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _prior_evidence(
    prior_context: Sequence[Mapping[str, object]],
) -> tuple[str, list[str]]:
    text_parts: list[str] = []
    metrics: list[str] = []
    for record in prior_context:
        context_type = str(record.get("context_type") or "")
        text_parts.extend(
            str(record.get(key) or "")
            for key in ("title", "rns_type")
        )
        if context_type == "company_memory_snapshot":
            for series in _dict_list(record.get("metric_series")):
                metrics.extend(
                    str(series.get(key) or "")
                    for key in ("metric", "label")
                )
            for item in _dict_list(record.get("current_guidance")):
                metrics.append(str(item.get("metric") or ""))
            for group in ("open_management_claims", "resolved_management_claims"):
                for item in _dict_list(record.get(group)):
                    metrics.extend(
                        str(item.get(key) or "")
                        for key in ("metric", "claim")
                    )
            continue
        if context_type == "prior_company_record":
            disclosure = record.get("company_disclosure")
            if not isinstance(disclosure, Mapping):
                continue
            for fact in _dict_list(disclosure.get("reported_facts")):
                metrics.extend(
                    str(fact.get(key) or "")
                    for key in ("metric", "label")
                )
            for event in _dict_list(disclosure.get("guidance_events")):
                metrics.append(str(event.get("metric") or ""))
            for claim in _dict_list(disclosure.get("management_claims")):
                metrics.extend(
                    str(claim.get(key) or "")
                    for key in ("metric", "claim")
                )
            continue
        # Raw records are supported for locked tests and one-off validation jobs.
        for fact in _dict_list(record.get("facts")):
            metrics.extend(
                str(fact.get(key) or "")
                for key in ("metric", "label")
            )
        for event in _dict_list(record.get("guidance")):
            metrics.append(str(event.get("metric") or ""))
        for claim in _dict_list(record.get("management_claims")):
            metrics.extend(
                str(claim.get(key) or "")
                for key in ("metric", "claim")
            )
    return " ".join(text_parts), [item for item in metrics if item.strip()]


def _priority_models(template: _ProfileTemplate) -> list[KPIPriority]:
    return [
        KPIPriority(metric=metric, role=role, why=why, aliases=list(aliases))
        for metric, role, why, aliases in template.priorities
    ]


def infer_kpi_profile(
    announcement: AnnouncementInput,
    prior_context: Sequence[Mapping[str, object]] = (),
) -> KPIProfileSnapshot:
    """Infer a cautious company archetype from supplied point-in-time evidence."""

    current_text = " ".join(
        (
            announcement.company,
            announcement.title,
            announcement.rns_type,
            " ".join(announcement.categories),
            announcement.text,
        )
    )
    prior_text, structured_metrics = _prior_evidence(prior_context)
    scored: list[tuple[int, int, _ProfileTemplate, list[str]]] = []

    for template in _PROFILES:
        score = 0
        matches: list[str] = []
        for term, weight in template.signals:
            if _contains(current_text, term):
                score += weight
                matches.append(f"current evidence: {term}")
            elif _contains(prior_text, term):
                score += max(1, weight // 2)
                matches.append(f"prior RNS title/type: {term}")
            metric_hits = sum(1 for metric in structured_metrics if _contains(metric, term))
            if metric_hits:
                score += min(8, metric_hits * max(2, weight // 2))
                matches.append(f"structured history: {term}")
        # A disclosed priority KPI is a strong classifier even when the wording
        # does not appear in the prose surrounding it.
        for metric, _role, _why, aliases in template.priorities:
            alias_hit = any(
                _contains(structured_metric, alias)
                for structured_metric in structured_metrics
                for alias in aliases
            )
            if alias_hit:
                score += 3
                matches.append(f"structured KPI: {metric}")
        scored.append((score, len(set(matches)), template, list(dict.fromkeys(matches))))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    top_score, _match_count, top, matches = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0
    ambiguous = top_score < 5 or (top_score < 11 and top_score - second_score <= 1)
    if ambiguous:
        return KPIProfileSnapshot(
            profile_id=_GENERIC.profile_id,
            label=_GENERIC.label,
            confidence=0.35 if top_score < 5 else 0.5,
            score=top_score,
            matched_signals=matches[:6],
            priority_kpis=_priority_models(_GENERIC),
            relationship_checks=list(_GENERIC.relationship_checks),
            sector_questions=list(_GENERIC.sector_questions),
        )

    separation = max(0, top_score - second_score)
    confidence = min(0.95, 0.48 + top_score * 0.025 + separation * 0.02)
    return KPIProfileSnapshot(
        profile_id=top.profile_id,
        label=top.label,
        confidence=round(confidence, 2),
        score=top_score,
        matched_signals=matches[:10],
        priority_kpis=_priority_models(top),
        relationship_checks=list(top.relationship_checks),
        sector_questions=list(top.sector_questions),
    )
