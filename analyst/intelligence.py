from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from analyst.kpi_profiles import KPIProfileSnapshot, infer_kpi_profile
from analyst.models import AnalystNote, AnnouncementInput, KeyFact, StrictModel

FindingSeverity = Literal["info", "review"]
FindingDirection = Literal["favourable", "adverse", "mixed", "unclear"]


class IntelligenceFinding(StrictModel):
    """Evidence-derived analytical tension supplied to the final review."""

    code: str
    title: str
    severity: FindingSeverity
    direction: FindingDirection
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    related_metrics: list[str] = Field(default_factory=list)
    surface_term_groups: list[list[str]] = Field(default_factory=list)


class AnalystIntelligenceBundle(StrictModel):
    context_type: Literal["analyst_intelligence_bundle"] = (
        "analyst_intelligence_bundle"
    )
    profile: KPIProfileSnapshot
    findings: list[IntelligenceFinding] = Field(default_factory=list)

    def to_review_record(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload["intelligence_rules"] = [
            "The sector profile is a heuristic checklist, not a company-reported fact.",
            "Each finding is derived from the structured draft and supplied evidence; verify it before changing the note.",
            "A valid finding should be surfaced proportionately in the headline, takeaway, analyst view, key facts or what-to-watch section.",
            "Do not invent a missing KPI or force a negative conclusion merely because a checklist item is absent.",
        ]
        return payload


@dataclass(frozen=True)
class _Movement:
    metric: str
    label: str
    current: float | None
    previous: float | None
    value_text: str
    previous_text: str
    unit: str
    currency: str
    basis: str
    change_percent: float | None
    change_absolute: float | None
    comparator_source_id: str


_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def _normalise(value: object) -> str:
    text = " ".join(str(value or "").lower().replace("&", " and ").split())
    output = []
    for char in text:
        output.append(char if char.isalnum() else " ")
    return " ".join("".join(output).split())


def _contains(value: object, term: str) -> bool:
    text = f" {_normalise(value)} "
    needle = _normalise(term)
    return bool(needle) and f" {needle} " in text


def _matches_any(value: object, aliases: Sequence[str]) -> bool:
    return any(_contains(value, alias) for alias in aliases)


def _parse_numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    match = _NUMBER_RE.search(text.replace("(", "-").replace(")", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _period_family(period: object, as_of_date: object = "") -> str:
    text = _normalise(period)
    if re.search(r"\bh1\b", text) or "first half" in text:
        return "h1"
    if re.search(r"\bh2\b", text) or "second half" in text:
        return "h2"
    quarter = re.search(r"\bq([1-4])\b", text)
    if quarter:
        return f"q{quarter.group(1)}"
    if "six months" in text or "half year" in text:
        return "half year"
    if re.search(r"\bfy\s*\d{2,4}\b", text) or "full year" in text or "year ended" in text:
        return "fy"
    if str(as_of_date or "").strip() or not text or text == "point in time":
        return "point in time"
    return text


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _memory_series(
    prior_context: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    for record in prior_context:
        if record.get("context_type") == "company_memory_snapshot":
            return _dict_list(record.get("metric_series"))
    return []


def _memory_comparator(
    fact: KeyFact,
    prior_context: Sequence[Mapping[str, object]],
) -> tuple[str, float | None, str]:
    metric = _normalise(fact.metric or fact.label)
    if not metric:
        return "", None, ""
    family = _period_family(fact.period, fact.as_of_date)
    unit = _normalise(fact.unit)
    currency = _normalise(fact.currency)
    basis = _normalise(fact.basis)
    candidates: list[dict[str, object]] = []
    for series in _memory_series(prior_context):
        if _normalise(series.get("metric")) != metric:
            continue
        if _normalise(series.get("period_family")) != family:
            continue
        if unit and _normalise(series.get("unit")) and _normalise(series.get("unit")) != unit:
            continue
        if currency and _normalise(series.get("currency")) and _normalise(series.get("currency")) != currency:
            continue
        if basis and _normalise(series.get("basis")) and _normalise(series.get("basis")) != basis:
            continue
        candidates.append(series)
    if not candidates:
        return "", None, ""
    points = _dict_list(candidates[0].get("points"))
    if not points:
        return "", None, ""
    latest = points[-1]
    value_text = str(latest.get("value") or "")
    return (
        value_text,
        _parse_numeric(latest.get("value_numeric")) or _parse_numeric(value_text),
        str(latest.get("source_id") or ""),
    )


def _fact_movement(
    fact: KeyFact,
    prior_context: Sequence[Mapping[str, object]],
) -> _Movement:
    metric = fact.metric or fact.label
    current = fact.value_numeric
    if current is None:
        current = _parse_numeric(fact.value)
    previous_text = fact.previous_value.strip()
    previous = _parse_numeric(previous_text)
    comparator_source_id = fact.comparator_source_id.strip()
    if previous is None:
        memory_text, memory_value, memory_source = _memory_comparator(
            fact,
            prior_context,
        )
        if memory_value is not None:
            previous_text = memory_text
            previous = memory_value
            comparator_source_id = comparator_source_id or memory_source

    descriptor = _normalise(f"{metric} {fact.label} {fact.value} {fact.unit}")
    is_percent = "%" in fact.value or _normalise(fact.unit) in {"percent", "percentage", "%"}
    is_margin = "margin" in descriptor or "rate" in descriptor or "yield" in descriptor
    direct_change = any(term in descriptor for term in ("growth", "change", "movement", "decline", "increase"))
    percentage_points = "percentage point" in descriptor or " pp " in f" {descriptor} " or fact.unit.lower() in {"pp", "ppt", "percentage points"}

    change_percent: float | None = None
    change_absolute: float | None = None
    if direct_change and current is not None and is_percent and previous is None:
        if is_margin and percentage_points:
            change_absolute = current
        else:
            change_percent = current
    elif current is not None and previous is not None:
        change_absolute = current - previous
        if not is_margin and previous != 0:
            change_percent = change_absolute / abs(previous) * 100

    return _Movement(
        metric=metric,
        label=fact.label,
        current=current,
        previous=previous,
        value_text=fact.value,
        previous_text=previous_text,
        unit=fact.unit,
        currency=fact.currency,
        basis=fact.basis,
        change_percent=change_percent,
        change_absolute=change_absolute,
        comparator_source_id=comparator_source_id,
    )


def _movements(
    note: AnalystNote,
    prior_context: Sequence[Mapping[str, object]],
) -> list[_Movement]:
    return [
        _fact_movement(fact, prior_context)
        for fact in note.key_facts
        if fact.basis in {"reported", "calculated"}
    ]


def _find(
    movements: Sequence[_Movement],
    aliases: Sequence[str],
    *,
    require_change: bool = True,
) -> _Movement | None:
    for movement in movements:
        descriptor = f"{movement.metric} {movement.label}"
        if not _matches_any(descriptor, aliases):
            continue
        if require_change and movement.change_percent is None and movement.change_absolute is None:
            continue
        return movement
    return None


def _movement_evidence(movement: _Movement) -> str:
    name = movement.label or movement.metric
    if movement.change_absolute is not None and _matches_any(
        f"{movement.metric} {movement.label}",
        ("margin", "rate", "yield"),
    ):
        return (
            f"{name}: {movement.value_text} versus {movement.previous_text} "
            f"({movement.change_absolute:+.1f} percentage points)."
        )
    if movement.change_percent is not None:
        if movement.previous_text:
            return (
                f"{name}: {movement.value_text} versus {movement.previous_text} "
                f"({movement.change_percent:+.1f}%)."
            )
        return f"{name}: disclosed change {movement.change_percent:+.1f}%."
    if movement.previous_text:
        return f"{name}: {movement.value_text} versus {movement.previous_text}."
    return f"{name}: {movement.value_text}."


def _note_text(note: AnalystNote) -> str:
    parts = [
        note.headline,
        note.takeaway,
        note.impact_rationale,
        note.what_changed.before,
        note.what_changed.today,
        note.what_changed.read_through,
        note.analyst_view,
        *note.new_information,
        *note.reiterated_information,
        *note.supports_case,
        *note.challenges_case,
        *note.watch_items,
        *note.disclosure_assessment.missing_items,
        note.disclosure_assessment.management_language_mismatch,
        note.disclosure_assessment.note,
    ]
    for fact in note.key_facts:
        parts.extend((fact.label, fact.metric, fact.value, fact.note, fact.comparator, fact.previous_value))
    return _normalise(" ".join(parts))


def _source_has(text: str, *terms: str) -> bool:
    normalised = _normalise(text)
    return any(_normalise(term) in normalised for term in terms)


def _topline_aliases(profile_id: str) -> tuple[str, ...]:
    return {
        "housebuilder": ("completions", "reservations", "revenue", "sales"),
        "property": ("rental income", "rent", "revenue"),
        "recruiter": ("net fee income", "nfi"),
        "software": ("arr", "annual recurring revenue", "recurring revenue", "revenue"),
        "lender": ("loan book", "originations"),
        "mining": ("production", "ounces", "tonnes"),
        "oil-gas": ("production", "boepd", "barrels"),
        "retailer": ("like for like", "lfl", "sales", "revenue"),
        "professional-services": ("fee income", "revenue", "net revenue"),
    }.get(profile_id, ("revenue", "sales", "net fee income", "arr"))


def _cash_deterioration(movements: Sequence[_Movement]) -> list[_Movement]:
    output: list[_Movement] = []
    debt = _find(movements, ("net debt", "borrowings", "debt"))
    if debt and debt.change_percent is not None and debt.change_percent >= 10:
        output.append(debt)
    cash = _find(movements, ("net cash", "cash balance", "cash"))
    if cash and cash.change_percent is not None and cash.change_percent <= -10:
        output.append(cash)
    conversion = _find(movements, ("cash conversion", "operating cash flow", "free cash flow"))
    if conversion:
        if conversion.change_percent is not None and conversion.change_percent <= -10:
            output.append(conversion)
        elif conversion.change_absolute is not None and conversion.change_absolute <= -5:
            output.append(conversion)
    return list(dict.fromkeys(output))


def _finding(
    *,
    code: str,
    title: str,
    severity: FindingSeverity,
    direction: FindingDirection,
    explanation: str,
    evidence: Sequence[str],
    related_metrics: Sequence[str],
    surface_term_groups: Sequence[Sequence[str]],
) -> IntelligenceFinding:
    return IntelligenceFinding(
        code=code,
        title=title,
        severity=severity,
        direction=direction,
        explanation=explanation,
        evidence=list(dict.fromkeys(evidence)),
        related_metrics=list(dict.fromkeys(related_metrics)),
        surface_term_groups=[list(group) for group in surface_term_groups],
    )


def detect_analytical_tensions(
    announcement: AnnouncementInput,
    note: AnalystNote,
    prior_context: Sequence[Mapping[str, object]] = (),
    *,
    profile: KPIProfileSnapshot | None = None,
) -> list[IntelligenceFinding]:
    """Detect evidence-backed relationships a human analyst would challenge."""

    profile = profile or infer_kpi_profile(announcement, prior_context)
    movements = _movements(note, prior_context)
    findings: list[IntelligenceFinding] = []
    topline = _find(movements, _topline_aliases(profile.profile_id))
    profit = _find(
        movements,
        ("adjusted ebitda", "ebitda", "operating profit", "profit before tax", "underlying profit", "pbt"),
    )
    margin = _find(
        movements,
        ("ebitda margin", "operating margin", "gross margin", "margin"),
    )
    cash_pressure = _cash_deterioration(movements)

    quality_evidence: list[str] = []
    if topline and topline.change_percent is not None and topline.change_percent >= 5:
        if margin and margin.change_absolute is not None and margin.change_absolute <= -0.5:
            quality_evidence.extend((_movement_evidence(topline), _movement_evidence(margin)))
        if profit and profit.change_percent is not None:
            lag = topline.change_percent - profit.change_percent
            if lag >= 10 or profit.change_percent < 0:
                quality_evidence.extend((_movement_evidence(topline), _movement_evidence(profit)))
    if quality_evidence:
        findings.append(
            _finding(
                code="GROWTH_QUALITY_DIVERGENCE",
                title="Top-line growth is not converting at the same rate",
                severity="review",
                direction="mixed",
                explanation=(
                    "Revenue or the sector's primary volume KPI improved, but profit or margin "
                    "did not keep pace. The note should lead with the weaker earnings quality "
                    "rather than treating growth as uniformly favourable."
                ),
                evidence=quality_evidence,
                related_metrics=[item.metric for item in (topline, profit, margin) if item],
                surface_term_groups=(
                    ("margin", "profit quality", "earnings quality", "profit"),
                    ("lower", "fell", "decline", "lag", "slower", "deterior", "pressure", "weaker"),
                ),
            )
        )

    if profit and profit.change_percent is not None and profit.change_percent >= 0 and cash_pressure:
        findings.append(
            _finding(
                code="EARNINGS_CASH_DIVERGENCE",
                title="Reported earnings and financial risk are moving in different directions",
                severity="review",
                direction="mixed",
                explanation=(
                    "Profit or EBITDA improved, but cash conversion, cash or net debt worsened. "
                    "The analyst view should separate accounting earnings from balance-sheet quality."
                ),
                evidence=[_movement_evidence(profit), *[_movement_evidence(item) for item in cash_pressure]],
                related_metrics=[profit.metric, *[item.metric for item in cash_pressure]],
                surface_term_groups=(
                    ("cash", "debt", "balance sheet", "working capital"),
                    ("worsen", "higher", "rose", "increase", "weaker", "lower", "fell", "strain"),
                ),
            )
        )

    maintained_guidance = any(
        event.status in {"maintained", "reiterated"}
        for event in note.guidance_events
    )
    if maintained_guidance and cash_pressure and not any(
        item.code == "EARNINGS_CASH_DIVERGENCE" for item in findings
    ):
        findings.append(
            _finding(
                code="GUIDANCE_BALANCE_SHEET_DIVERGENCE",
                title="Guidance is unchanged but financial risk worsened",
                severity="review",
                direction="mixed",
                explanation=(
                    "Maintained earnings guidance does not cancel out weaker cash or debt. "
                    "The note should make clear that the change is in financial risk, not expectations."
                ),
                evidence=[
                    "Company guidance is maintained or reiterated.",
                    *[_movement_evidence(item) for item in cash_pressure],
                ],
                related_metrics=[item.metric for item in cash_pressure],
                surface_term_groups=(
                    ("guidance", "expectations"),
                    ("cash", "debt", "balance sheet"),
                ),
            )
        )

    order_book = _find(movements, ("order book", "backlog", "book to bill"))
    if order_book and order_book.change_percent is not None and order_book.change_percent >= 10:
        adverse_delivery = []
        if profit and profit.change_percent is not None and profit.change_percent < 0:
            adverse_delivery.append(profit)
        if margin and margin.change_absolute is not None and margin.change_absolute < 0:
            adverse_delivery.append(margin)
        if adverse_delivery:
            findings.append(
                _finding(
                    code="BACKLOG_QUALITY_DIVERGENCE",
                    title="A larger order book has not yet improved current economics",
                    severity="review",
                    direction="mixed",
                    explanation=(
                        "Backlog is stronger, but current profit or margin is weaker. Treat the order "
                        "book as future delivery evidence, not proof that earnings quality has improved."
                    ),
                    evidence=[_movement_evidence(order_book), *[_movement_evidence(item) for item in adverse_delivery]],
                    related_metrics=[order_book.metric, *[item.metric for item in adverse_delivery]],
                    surface_term_groups=(
                        ("order book", "backlog"),
                        ("margin", "profit", "delivery", "conversion"),
                    ),
                )
            )

    source_text = announcement.text
    acquisition_led = _source_has(
        source_text,
        "contribution from acquisitions",
        "contributions from acquisitions",
        "acquisition contribution",
        "acquired businesses",
        "buy and build",
    )
    organic_disclosed = _source_has(source_text, "organic growth", "organically") or any(
        _matches_any(f"{fact.metric} {fact.label}", ("organic growth", "organic revenue"))
        for fact in note.key_facts
    )
    if acquisition_led and not organic_disclosed:
        findings.append(
            _finding(
                code="ACQUISITION_ORGANIC_GAP",
                title="Acquisitions contributed to growth but organic performance is unclear",
                severity="info",
                direction="unclear",
                explanation=(
                    "The source attributes some growth to acquisitions without quantifying the "
                    "underlying organic contribution. The note should not present all growth as like-for-like progress."
                ),
                evidence=["The current RNS attributes part of growth to acquisitions."],
                related_metrics=[topline.metric] if topline else ["organic growth"],
                surface_term_groups=(
                    ("organic",),
                    ("not disclosed", "unclear", "not quantified", "unknown"),
                ),
            )
        )

    if profile.profile_id == "recruiter" and "trading" in _normalise(announcement.rns_type + " " + announcement.title):
        note_has_nfi = any(
            _matches_any(f"{fact.metric} {fact.label}", ("net fee income", "nfi"))
            for fact in note.key_facts
        )
        source_has_nfi = _source_has(source_text, "net fee income", " nfi ")
        source_has_gross = _source_has(source_text, "gross billings", "contractor billings", "reported revenue")
        if source_has_nfi and not note_has_nfi:
            findings.append(
                _finding(
                    code="SECTOR_PRIMARY_KPI_OMITTED",
                    title="The recruiter KPI that matters was disclosed but not prioritised",
                    severity="review",
                    direction="unclear",
                    explanation=(
                        "Net fee income is the economically meaningful recruiter top line. Gross contractor "
                        "billings or pass-through revenue should not lead the analysis when NFI is available."
                    ),
                    evidence=["The current RNS discloses net fee income."],
                    related_metrics=["net fee income"],
                    surface_term_groups=(("net fee income", "nfi"),),
                )
            )
        elif source_has_gross and not source_has_nfi and not note_has_nfi:
            findings.append(
                _finding(
                    code="RECRUITER_NFI_NOT_DISCLOSED",
                    title="Gross recruiter revenue is disclosed without net fee income",
                    severity="info",
                    direction="unclear",
                    explanation=(
                        "Gross contractor revenue can include payroll pass-through. Flag that net fee income, "
                        "the more useful economic KPI, is not available in the evidence."
                    ),
                    evidence=["The source discloses gross recruiter revenue or billings without NFI."],
                    related_metrics=["net fee income"],
                    surface_term_groups=(
                        ("net fee income", "nfi"),
                        ("not disclosed", "unavailable", "unclear"),
                    ),
                )
            )

    funding_markers = [
        marker
        for marker in (
            "require further funding",
            "requires further funding",
            "additional funding",
            "funding requirement",
            "no binding financing",
            "cash runway",
            "insufficient working capital",
        )
        if _source_has(source_text, marker)
    ]
    if profile.profile_id == "life-sciences" and funding_markers:
        findings.append(
            _finding(
                code="LIFE_SCIENCE_FUNDING_GAP",
                title="Funding capacity is part of the investment event",
                severity="review",
                direction="adverse",
                explanation=(
                    "For a loss-making life-sciences company, technical progress must be assessed alongside "
                    "the cash required to reach the next milestone. Financing discussions are not the same as committed funding."
                ),
                evidence=[f"Source funding marker: {marker}." for marker in funding_markers],
                related_metrics=["cash runway", "funding"],
                surface_term_groups=(
                    ("funding", "cash runway", "working capital", "cash"),
                    ("need", "require", "not agreed", "not binding", "risk", "uncertain"),
                ),
            )
        )

    if profile.profile_id == "lender":
        loan_book = _find(movements, ("loan book", "originations"))
        risk = _find(movements, ("cost of risk", "arrears", "impairment", "credit loss"))
        if (
            loan_book
            and loan_book.change_percent is not None
            and loan_book.change_percent >= 10
            and risk
            and (
                (risk.change_percent is not None and risk.change_percent > 0)
                or (risk.change_absolute is not None and risk.change_absolute > 0)
            )
        ):
            findings.append(
                _finding(
                    code="LENDING_GROWTH_RISK_DIVERGENCE",
                    title="Loan growth is accompanied by weaker credit indicators",
                    severity="review",
                    direction="mixed",
                    explanation=(
                        "Faster lending growth is not uniformly favourable when arrears, impairments or cost of risk also rise."
                    ),
                    evidence=[_movement_evidence(loan_book), _movement_evidence(risk)],
                    related_metrics=[loan_book.metric, risk.metric],
                    surface_term_groups=(
                        ("loan book", "lending", "originations"),
                        ("arrears", "impairment", "credit", "cost of risk"),
                    ),
                )
            )

    if profile.profile_id == "software":
        recurring = _find(movements, ("arr", "annual recurring revenue", "recurring revenue"))
        churn = _find(movements, ("churn", "retention"))
        software_adverse = list(cash_pressure)
        if churn and (
            ("churn" in _normalise(churn.metric) and (churn.change_percent or churn.change_absolute or 0) > 0)
            or ("retention" in _normalise(churn.metric) and (churn.change_percent or churn.change_absolute or 0) < 0)
        ):
            software_adverse.append(churn)
        if recurring and recurring.change_percent is not None and recurring.change_percent >= 10 and software_adverse:
            findings.append(
                _finding(
                    code="RECURRING_GROWTH_CASH_RISK",
                    title="Recurring growth is not yet translating into stronger cash quality",
                    severity="review",
                    direction="mixed",
                    explanation=(
                        "ARR growth should be assessed alongside retention, cash burn and funding capacity rather than in isolation."
                    ),
                    evidence=[_movement_evidence(recurring), *[_movement_evidence(item) for item in software_adverse]],
                    related_metrics=[recurring.metric, *[item.metric for item in software_adverse]],
                    surface_term_groups=(
                        ("arr", "recurring revenue"),
                        ("cash", "burn", "debt", "churn", "retention"),
                    ),
                )
            )

    if profile.profile_id in {"mining", "oil-gas"}:
        production = _find(movements, ("production", "boepd", "ounces", "tonnes", "barrels"))
        cost = _find(movements, ("aisc", "cash cost", "lifting cost", "unit cost", "operating cost"))
        if (
            production
            and production.change_percent is not None
            and production.change_percent >= 5
            and cost
            and cost.change_percent is not None
            and cost.change_percent >= 5
        ):
            findings.append(
                _finding(
                    code="PRODUCTION_COST_DIVERGENCE",
                    title="Higher production is being partly offset by higher unit costs",
                    severity="review",
                    direction="mixed",
                    explanation=(
                        "Physical output improved, but unit costs also rose. The note should explain the effect on cash margin and repeatability."
                    ),
                    evidence=[_movement_evidence(production), _movement_evidence(cost)],
                    related_metrics=[production.metric, cost.metric],
                    surface_term_groups=(
                        ("production",),
                        ("cost", "aisc", "lifting"),
                    ),
                )
            )

    if profile.profile_id == "retailer":
        sales = _find(movements, ("like for like", "lfl", "sales", "revenue"))
        inventory = _find(movements, ("inventory", "stock"))
        retail_adverse: list[_Movement] = []
        if margin and margin.change_absolute is not None and margin.change_absolute < 0:
            retail_adverse.append(margin)
        if inventory and inventory.change_percent is not None and inventory.change_percent >= 10:
            retail_adverse.append(inventory)
        if sales and sales.change_percent is not None and sales.change_percent >= 5 and retail_adverse:
            findings.append(
                _finding(
                    code="SALES_MARGIN_STOCK_DIVERGENCE",
                    title="Sales growth is accompanied by margin or inventory pressure",
                    severity="review",
                    direction="mixed",
                    explanation=(
                        "Retail sales growth is lower quality when gross margin falls or inventory rises materially faster."
                    ),
                    evidence=[_movement_evidence(sales), *[_movement_evidence(item) for item in retail_adverse]],
                    related_metrics=[sales.metric, *[item.metric for item in retail_adverse]],
                    surface_term_groups=(
                        ("sales", "like for like", "lfl"),
                        ("margin", "inventory", "stock"),
                    ),
                )
            )

    deduped: list[IntelligenceFinding] = []
    seen: set[str] = set()
    for finding in findings:
        if finding.code in seen:
            continue
        seen.add(finding.code)
        deduped.append(finding)
    deduped.sort(key=lambda item: (item.severity == "review", item.code), reverse=True)
    return deduped[:8]


def finding_is_resolved(finding: IntelligenceFinding, note: AnalystNote) -> bool:
    if not finding.surface_term_groups:
        return True
    text = _note_text(note)
    return all(
        any(_normalise(term) in text for term in group)
        for group in finding.surface_term_groups
    )


def unresolved_intelligence_findings(
    announcement: AnnouncementInput,
    note: AnalystNote,
    prior_context: Sequence[Mapping[str, object]] = (),
) -> tuple[KPIProfileSnapshot, list[IntelligenceFinding]]:
    profile = infer_kpi_profile(announcement, prior_context)
    findings = detect_analytical_tensions(
        announcement,
        note,
        prior_context,
        profile=profile,
    )
    unresolved = [item for item in findings if not finding_is_resolved(item, note)]
    return profile, unresolved
