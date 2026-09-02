from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal

KPI_INTEGRITY_VERSION = "kpi-integrity-v1"

PeriodType = Literal["instant", "duration", "event", "unknown"]
TrendStatus = Literal[
    "comparable",
    "single-point",
    "range-only",
    "insufficient-period",
    "missing-provenance",
    "non-numeric",
]


@dataclass(frozen=True, slots=True)
class MetricIdentity:
    key: str
    metric: str
    label: str
    instant: bool = False


@dataclass(frozen=True, slots=True)
class PeriodProfile:
    key: str
    label: str
    kind: PeriodType
    end: str
    year: int | None
    sort_at: datetime | None
    confidence: str


@dataclass(frozen=True, slots=True)
class UnitProfile:
    family: str
    currency: str
    scale: float
    confidence: str


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalise(value: object) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = text.replace("£", " gbp ").replace("$", " usd ").replace("€", " eur ")
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", text).split())


def _slug(value: object) -> str:
    return "-".join(_normalise(value).replace("%", " percent ").split())


def _number(value: object) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = _clean(value)
        if not raw:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _date(value: object) -> date | None:
    raw = _clean(value)
    if not raw:
        return None
    iso = re.search(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b", raw)
    if iso:
        try:
            return date.fromisoformat(iso.group(0))
        except ValueError:
            pass
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})\b", raw)
    if numeric:
        day, month, year = (int(item) for item in numeric.groups())
        try:
            return date(year, month, day)
        except ValueError:
            pass
    cleaned = re.sub(
        r"(?i)\b(?:as at|as of|at|for the (?:year|period) ended|year ended|period ended|ended)\b",
        " ",
        raw,
    )
    cleaned = " ".join(cleaned.replace(",", " ").split())
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _year(normalised: str) -> int | None:
    match = re.search(r"\bfy\s*(\d{2,4})\b", normalised)
    raw = match.group(1) if match else ""
    if not raw:
        years = re.findall(r"\b(?:19|20)\d{2}\b", normalised)
        raw = years[-1] if years else ""
    if not raw:
        return None
    parsed = int(raw)
    if parsed < 100:
        return 2000 + parsed if parsed <= 69 else 1900 + parsed
    return parsed


def _strip_metric_metadata(value: object) -> str:
    raw = _clean(value)
    if not raw:
        return ""

    known_units = {
        "gbp",
        "gbp m",
        "gbp million",
        "usd",
        "usd m",
        "eur",
        "eur m",
        "m",
        "mn",
        "million",
        "k",
        "000",
        "thousand",
        "bn",
        "billion",
        "%",
        "percent",
        "pp",
        "bps",
        "x",
        "shares",
        "million shares",
    }

    def remove_parenthetical(match: re.Match[str]) -> str:
        return " " if _normalise(match.group(1)) in known_units else match.group(0)

    raw = re.sub(r"\(([^()]*)\)", remove_parenthetical, raw)
    raw = re.sub(
        r"(?i)^\s*(?:(?:q[1-4]|h[12]|fy)\s*[-/]?\s*\d{2,4}\s*[:\-–—]?\s*)+",
        "",
        raw,
    )
    raw = re.sub(
        r"(?i)\s*[\(\[\-–—,:]?\s*(?:q[1-4]|h[12]|fy)\s*[-/]?\s*\d{2,4}\s*[\)\]]?\s*$",
        "",
        raw,
    )
    return _clean(raw).strip("-–—:;, ")


_RULES: tuple[tuple[MetricIdentity, tuple[str, ...]], ...] = (
    (
        MetricIdentity("net-debt", "net debt", "Net debt", True),
        ("net debt", "net borrowings", "net financial debt"),
    ),
    (MetricIdentity("net-cash", "net cash", "Net cash", True), ("net cash", "net funds")),
    (
        MetricIdentity("cash", "cash", "Cash", True),
        ("cash", "cash balance", "cash and cash equivalents"),
    ),
    (
        MetricIdentity("liquidity", "liquidity", "Liquidity", True),
        ("liquidity", "available liquidity"),
    ),
    (MetricIdentity("revenue", "revenue", "Revenue"), ("revenue", "group revenue", "turnover")),
    (MetricIdentity("recurring-revenue", "recurring revenue", "Recurring revenue"), ("recurring revenue",)),
    (
        MetricIdentity("arr", "annual recurring revenue", "Annual recurring revenue", True),
        ("annual recurring revenue", "arr"),
    ),
    (MetricIdentity("nfi", "net fee income", "Net fee income"), ("net fee income", "nfi")),
    (MetricIdentity("ebitda", "ebitda", "EBITDA"), ("ebitda", "reported ebitda")),
    (MetricIdentity("adjusted-ebitda", "adjusted ebitda", "Adjusted EBITDA"), ("adjusted ebitda",)),
    (MetricIdentity("ebitda-margin", "ebitda margin", "EBITDA margin"), ("ebitda margin",)),
    (
        MetricIdentity("adjusted-ebitda-margin", "adjusted ebitda margin", "Adjusted EBITDA margin"),
        ("adjusted ebitda margin",),
    ),
    (
        MetricIdentity("pbt", "profit before tax", "Profit before tax"),
        ("profit before tax", "pbt", "statutory profit before tax"),
    ),
    (
        MetricIdentity("adjusted-pbt", "adjusted profit before tax", "Adjusted profit before tax"),
        ("adjusted profit before tax", "adjusted pbt"),
    ),
    (MetricIdentity("operating-profit", "operating profit", "Operating profit"), ("operating profit",)),
    (MetricIdentity("gross-margin", "gross margin", "Gross margin"), ("gross margin",)),
    (MetricIdentity("operating-margin", "operating margin", "Operating margin"), ("operating margin",)),
    (MetricIdentity("free-cash-flow", "free cash flow", "Free cash flow"), ("free cash flow", "fcf")),
    (MetricIdentity("cash-conversion", "cash conversion", "Cash conversion"), ("cash conversion",)),
    (MetricIdentity("order-book", "order book", "Order book", True), ("order book",)),
    (MetricIdentity("backlog", "backlog", "Backlog", True), ("backlog",)),
    (MetricIdentity("loan-book", "loan book", "Loan book", True), ("loan book",)),
    (
        MetricIdentity("aum", "assets under management", "Assets under management", True),
        ("assets under management", "aum"),
    ),
    (MetricIdentity("nav", "net asset value", "Net asset value", True), ("net asset value", "nav")),
    (MetricIdentity("inventory", "inventory", "Inventory", True), ("inventory",)),
    (MetricIdentity("ltv", "loan to value", "Loan to value", True), ("loan to value", "ltv")),
    (MetricIdentity("basic-eps", "basic eps", "Basic EPS"), ("basic eps", "basic earnings per share")),
    (
        MetricIdentity("adjusted-eps", "adjusted eps", "Adjusted EPS"),
        ("adjusted eps", "adjusted earnings per share"),
    ),
    (MetricIdentity("dps", "dividend per share", "Dividend per share"), ("dividend per share", "dps")),
    (
        MetricIdentity("shares-in-issue", "shares in issue", "Shares in issue", True),
        ("shares in issue", "ordinary shares in issue"),
    ),
    (
        MetricIdentity("voting-rights", "total voting rights", "Total voting rights", True),
        ("total voting rights", "voting rights"),
    ),
    (MetricIdentity("completions", "completions", "Completions"), ("completions",)),
    (MetricIdentity("production", "production", "Production"), ("production",)),
    (MetricIdentity("aisc", "all in sustaining cost", "AISC"), ("all in sustaining cost", "aisc")),
    (MetricIdentity("recovery", "recovery", "Recovery"), ("recovery", "recovery rate")),
)
_ALIASES = {
    _normalise(alias): identity
    for identity, aliases in _RULES
    for alias in aliases
}


def metric_identity(metric: object, label: object = "") -> MetricIdentity:
    source = _strip_metric_metadata(metric) or _strip_metric_metadata(label)
    normalised = _normalise(source)
    if normalised in _ALIASES:
        return _ALIASES[normalised]
    display = _strip_metric_metadata(label) or source or "Metric"
    instant = any(
        phrase in normalised
        for phrase in (
            "cash balance",
            "debt balance",
            "borrowings",
            "headcount",
            "order book",
            "backlog",
            "inventory",
            "shares in issue",
            "voting rights",
            "assets under management",
            "net asset value",
        )
    )
    return MetricIdentity(
        _slug(normalised) or "metric",
        normalised or "metric",
        display,
        instant,
    )


def _duration_family(normalised: str, raw: str) -> tuple[str, str]:
    weeks = re.search(r"\b(5[23])\s+weeks?\b", normalised)
    if weeks:
        return f"FY{weeks.group(1)}W", "high"
    if re.search(r"\bh1\b", normalised) or "first half" in normalised:
        return "H1", "high"
    if re.search(r"\bh2\b", normalised) or "second half" in normalised:
        return "H2", "high"
    quarter = re.search(r"\bq([1-4])\b", normalised)
    if quarter:
        return f"Q{quarter.group(1)}", "high"
    if (
        re.search(r"\bfy\s*\d{2,4}\b", normalised)
        or "full year" in normalised
        or "year ended" in normalised
        or "twelve months" in normalised
    ):
        return "FY", "high"
    if "half year" in normalised or "half-year" in raw.lower():
        return "HY", "medium"
    months = re.search(r"\b(\d{1,2})\s+months?\b", normalised)
    if months:
        return f"{int(months.group(1))}M", "high"
    words = {"three months": "3M", "six months": "6M", "nine months": "9M"}
    for phrase, family in words.items():
        if phrase in normalised:
            return family, "high"
    if "year to date" in normalised or re.search(r"\bytd\b", normalised):
        return "YTD", "medium"
    if re.fullmatch(r"(?:fy\s*)?(?:19|20)?\d{2}", normalised):
        return "CY", "medium"
    return "UNKNOWN", "low"


def _sort_date(end: date | None, year: int | None, family: str) -> datetime | None:
    if end:
        return datetime(end.year, end.month, end.day, tzinfo=timezone.utc)
    if year is None:
        return None
    month, day = {
        "Q1": (3, 31),
        "Q2": (6, 30),
        "Q3": (9, 30),
        "H1": (6, 30),
        "HY": (6, 30),
        "3M": (3, 31),
        "6M": (6, 30),
        "9M": (9, 30),
    }.get(family, (12, 31))
    return datetime(year, month, day, tzinfo=timezone.utc)


def period_profile(
    period: object,
    as_of_date: object = "",
    *,
    instant_hint: bool = False,
) -> PeriodProfile:
    raw = _clean(period)
    normalised = _normalise(raw)
    end = _date(as_of_date) or _date(raw)
    year = end.year if end else _year(normalised)
    duration, duration_confidence = _duration_family(normalised, raw)
    event = any(
        term in normalised
        for term in (
            "transaction",
            "current authority",
            "possible offer",
            "contract",
            "programme",
            "award",
        )
    )
    explicit_point = bool(
        as_of_date
        or re.search(r"\b(?:point in time|instant|as at|as of)\b", normalised)
    )

    if event:
        key, label, kind, confidence, sort_family = (
            f"EVENT:{_slug(normalised) or 'event'}",
            "",
            "event",
            "high",
            "EVENT",
        )
    elif explicit_point or instant_hint:
        key, label, kind = "POINT", "Point in time", "instant"
        confidence = (
            "high"
            if end
            else "medium"
            if duration != "UNKNOWN" or year
            else "low"
        )
        sort_family = duration if duration != "UNKNOWN" else "POINT"
    elif duration != "UNKNOWN":
        key, label, kind, confidence, sort_family = (
            duration,
            duration,
            "duration",
            duration_confidence,
            duration,
        )
    else:
        key, label, kind, confidence, sort_family = (
            "UNKNOWN",
            "",
            "unknown",
            "low",
            "UNKNOWN",
        )

    return PeriodProfile(
        key=key,
        label=label,
        kind=kind,  # type: ignore[arg-type]
        end=end.isoformat() if end else "",
        year=year,
        sort_at=_sort_date(end, year, sort_family),
        confidence=confidence,
    )


def _currency(currency: object, unit: object, value: object) -> str:
    raw = _clean(currency)
    if raw == "GBp":
        return "GBp"
    aliases = {
        "gbp": "GBP",
        "£": "GBP",
        "sterling": "GBP",
        "usd": "USD",
        "$": "USD",
        "eur": "EUR",
        "€": "EUR",
        "cad": "CAD",
        "aud": "AUD",
        "zar": "ZAR",
        "pence": "GBp",
    }
    if raw.lower() in aliases:
        return aliases[raw.lower()]
    if re.fullmatch(r"[A-Za-z]{3}", raw):
        return raw.upper()
    combined = f"{_clean(unit)} {_clean(value)}"
    for symbol, code in (("£", "GBP"), ("$", "USD"), ("€", "EUR")):
        if symbol in combined:
            return code
    normalised = _normalise(combined)
    for alias, code in aliases.items():
        if alias.isalpha() and re.search(rf"\b{re.escape(alias)}\b", normalised):
            return code
    return ""


def unit_profile(
    unit: object,
    currency: object,
    value: object,
    *,
    identity: MetricIdentity,
) -> UnitProfile:
    raw_unit = _clean(unit)
    raw_value = _clean(value)
    unit_key = _normalise(raw_unit)
    combined = _normalise(f"{raw_unit} {raw_value}")
    currency_key = _currency(currency, raw_unit, raw_value)

    if (
        re.search(r"\b(?:billion|bn)\b", combined)
        or unit_key in {"gbp bn", "usd bn", "eur bn"}
    ):
        scale = 1_000_000_000.0
    elif (
        re.search(r"\b(?:million|mn)\b", combined)
        or re.search(r"(?i)(?:£|\$|€)?\s*[-+]?\d[\d,.]*\s*m\b", raw_value)
        or unit_key in {"gbp m", "usd m", "eur m"}
        or unit_key == "m"
        and (
            currency_key
            or identity.key
            in {
                "net-debt",
                "net-cash",
                "cash",
                "liquidity",
                "revenue",
                "ebitda",
                "adjusted-ebitda",
                "pbt",
                "adjusted-pbt",
                "operating-profit",
                "free-cash-flow",
                "order-book",
                "loan-book",
                "aum",
                "nav",
            }
        )
    ):
        scale = 1_000_000.0
    elif (
        re.search(r"\b(?:thousand|000)\b", combined)
        or re.search(r"(?i)(?:£|\$|€)?\s*[-+]?\d[\d,.]*\s*k\b", raw_value)
        or unit_key in {"k", "gbp k", "usd k", "eur k"}
    ):
        scale = 1_000.0
    else:
        scale = 1.0

    if re.search(r"\b(?:basis points?|bps)\b", combined):
        return UnitProfile("percentage-point", "", 0.01, "high")
    if re.search(r"\b(?:percentage points?|pp)\b", combined) or re.search(
        r"(?i)[-+]?\d[\d,.]*\s*pp\b",
        raw_value,
    ):
        return UnitProfile("percentage-point", "", 1.0, "high")
    if "%" in raw_unit or "%" in raw_value or re.search(
        r"\b(?:percent|percentage)\b",
        combined,
    ):
        return UnitProfile("percent", "", 1.0, "high")
    if re.search(r"(?i)[-+]?\d[\d,.]*\s*x\b", raw_value) or unit_key in {
        "x",
        "times",
        "multiple",
    }:
        return UnitProfile("multiple", "", 1.0, "high")
    if re.search(r"\bshares?\b", combined):
        return UnitProfile("shares", "", scale, "high")
    if currency_key:
        return UnitProfile("currency", currency_key, scale, "high")
    for pattern, family in (
        (r"\bdays?\b", "days"),
        (r"\b(?:tonnes?|tons?)\b", "tonnes"),
        (r"\bounces?\b", "ounces"),
        (r"\bboepd\b", "boepd"),
        (r"\bbarrels?\b", "barrels"),
        (r"\b(?:units?|homes?|customers?|employees?|headcount)\b", "count"),
    ):
        if re.search(pattern, combined):
            return UnitProfile(family, "", scale, "high")
    if unit_key in {
        "m",
        "mn",
        "million",
        "k",
        "thousand",
        "000",
        "bn",
        "billion",
        "",
    }:
        return UnitProfile("number", "", scale, "medium" if unit_key else "low")
    return UnitProfile(_slug(raw_unit) or "number", "", scale, "medium")


def _exact(point: Mapping[str, object]) -> float | None:
    numeric = _number(point.get("value_numeric"))
    if numeric is not None:
        return numeric
    low, high = _number(point.get("value_low")), _number(point.get("value_high"))
    if (
        low is not None
        and high is not None
        and math.isclose(low, high, abs_tol=1e-12)
    ):
        return low
    return None


def _numeric_kind(point: Mapping[str, object]) -> str:
    if _exact(point) is not None:
        return "exact"
    if _number(point.get("value_low")) is not None or _number(
        point.get("value_high")
    ) is not None:
        return "range"
    return "non-numeric"


def _point(
    raw: Mapping[str, object],
    series: Mapping[str, object],
    series_rank: int,
    point_rank: int,
) -> dict[str, Any] | None:
    metric = (
        _clean(raw.get("metric"))
        or _clean(series.get("metric"))
        or _clean(raw.get("label"))
        or _clean(series.get("label"))
    )
    label = _clean(raw.get("label")) or _clean(series.get("label")) or metric
    value = _clean(raw.get("value"))
    if not metric or not value or value.lower() == "not disclosed":
        return None

    identity = metric_identity(metric, label)
    period = _clean(raw.get("period"))
    as_of = _clean(raw.get("as_of_date"))
    period_meta = period_profile(period, as_of, instant_hint=identity.instant)
    unit_meta = unit_profile(
        raw.get("unit") or series.get("unit"),
        raw.get("currency") or series.get("currency"),
        value,
        identity=identity,
    )
    basis = _slug(raw.get("basis") or series.get("basis") or "reported") or "reported"
    exact = _exact(raw)
    published = _datetime(raw.get("published_at"))
    source_id, source_url = _clean(raw.get("source_id")), _clean(raw.get("source_url"))

    period_normalised = _normalise(period)
    if period_meta.kind == "instant":
        generic = {"", "point in time", "instant", "current", "latest"}
        slot = period_meta.end
        if not slot and period_normalised not in generic:
            slot = f"POINT:{period_normalised}"
        if not slot:
            slot = (
                published.date().isoformat()
                if published.year != datetime.min.year
                else source_id
            )
    else:
        slot = (
            period_meta.end
            or (
                f"{period_meta.key}:{period_meta.year}"
                if period_meta.year
                else ""
            )
            or period_normalised
        )
    if period_meta.kind in {"event", "unknown"} and not slot:
        slot = source_id or f"{series_rank}:{point_rank}"

    return {
        "source_id": source_id,
        "published_at": (
            published.isoformat()
            if published.year != datetime.min.year
            else _clean(raw.get("published_at"))
        ),
        "title": _clean(raw.get("title")),
        "source_url": source_url,
        "label": identity.label,
        "metric": identity.metric,
        "identity": identity.key,
        "period": period,
        "period_family": period_meta.label,
        "period_type": period_meta.kind,
        "period_end": period_meta.end,
        "value": value,
        "value_numeric": _number(raw.get("value_numeric")),
        "value_low": _number(raw.get("value_low")),
        "value_high": _number(raw.get("value_high")),
        "unit": _clean(raw.get("unit") or series.get("unit")),
        "unit_family": unit_meta.family,
        "unit_scale": unit_meta.scale,
        "comparable_value_numeric": (
            exact * unit_meta.scale if exact is not None else None
        ),
        "currency": unit_meta.currency,
        "as_of_date": as_of,
        "basis": basis,
        "note": _clean(raw.get("note")),
        "_period_key": period_meta.key,
        "_comparison_key": "|".join(
            (
                identity.key,
                period_meta.key,
                unit_meta.family,
                unit_meta.currency or "-",
                basis,
            )
        ),
        "_slot": slot,
        "_numeric_kind": _numeric_kind(raw),
        "_effective": period_meta.sort_at or published,
        "_published": published,
        "_series_rank": series_rank,
        "_point_rank": point_rank,
    }


def _public_point(point: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "source_id",
        "published_at",
        "title",
        "source_url",
        "label",
        "metric",
        "identity",
        "period",
        "period_family",
        "period_type",
        "period_end",
        "value",
        "value_numeric",
        "value_low",
        "value_high",
        "unit",
        "unit_family",
        "unit_scale",
        "comparable_value_numeric",
        "currency",
        "as_of_date",
        "basis",
        "note",
    )
    return {key: point[key] for key in keys}


def _dedupe(points: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: dict[str, dict[str, Any]] = {}
    for point in points:
        slot = point["_slot"] or point["source_id"] or str(point["_point_rank"])
        existing = slots.get(slot)
        if existing is None or (
            point["_published"],
            point["_series_rank"],
            point["_point_rank"],
        ) >= (
            existing["_published"],
            existing["_series_rank"],
            existing["_point_rank"],
        ):
            slots[slot] = point
    return sorted(
        slots.values(),
        key=lambda item: (
            item["_effective"],
            item["_published"],
            item["_series_rank"],
            item["_point_rank"],
        ),
    )


def _warnings(groups: Sequence[Sequence[dict[str, Any]]]) -> list[str]:
    checks = (
        (
            "INCOMPATIBLE_PERIOD",
            {group[-1]["_period_key"] for group in groups if group},
        ),
        (
            "INCOMPATIBLE_UNIT",
            {group[-1]["unit_family"] for group in groups if group},
        ),
        (
            "INCOMPATIBLE_CURRENCY",
            {group[-1]["currency"] for group in groups if group},
        ),
        (
            "INCOMPATIBLE_BASIS",
            {group[-1]["basis"] for group in groups if group},
        ),
    )
    return [code for code, values in checks if len(values) > 1]


def _status(
    points: Sequence[dict[str, Any]],
    exact: Sequence[dict[str, Any]],
) -> tuple[TrendStatus, str]:
    latest = points[-1]
    if latest["_numeric_kind"] == "range":
        return (
            "range-only",
            "The latest disclosure is a range, so no point trend is drawn.",
        )
    if latest["_numeric_kind"] == "non-numeric":
        return "non-numeric", "The latest disclosure is not an exact number."
    if latest["period_type"] in {"event", "unknown"}:
        return (
            "insufficient-period",
            "Period metadata is not precise enough for a like-for-like trend.",
        )
    if any(not point["source_id"] or not point["source_url"] for point in exact):
        return (
            "missing-provenance",
            "A trend is withheld because an observation lacks source provenance.",
        )
    if len(exact) < 2:
        return "single-point", "Only one comparable exact observation is available."
    return (
        "comparable",
        "Metric identity, period, unit, currency and basis are like for like.",
    )


def _series(
    points: Sequence[dict[str, Any]],
    identity_total: int,
    group_total: int,
    warnings: list[str],
) -> dict[str, Any]:
    selected = _dedupe(points)
    latest = selected[-1]
    exact = [
        point
        for point in selected
        if point["comparable_value_numeric"] is not None
        and point["period_type"] not in {"event", "unknown"}
    ]
    status, reason = _status(selected, exact)
    trend = exact[-8:] if status == "comparable" else []
    previous = trend[-2] if len(trend) >= 2 else None

    direction, absolute, percent = "unclear", None, None
    if previous:
        latest_base = trend[-1]["comparable_value_numeric"]
        previous_base = previous["comparable_value_numeric"]
        delta = latest_base - previous_base
        absolute = delta / (latest["unit_scale"] or 1.0)
        tolerance = max(abs(previous_base), 1.0) * 1e-9
        direction = (
            "flat"
            if abs(delta) <= tolerance
            else "up"
            if delta > 0
            else "down"
        )
        percent = delta / abs(previous_base) * 100.0 if previous_base else None

    suppressed = max(0, identity_total - len(points))
    if suppressed:
        verb = "remains" if suppressed == 1 else "remain"
        reason += (
            f" {suppressed} observation"
            f"{'s' if suppressed != 1 else ''} from a different period, unit, "
            f"currency or basis {verb} separate."
        )

    sources = {point["source_id"] for point in selected if point["source_id"]}
    integrity = {
        "version": KPI_INTEGRITY_VERSION,
        "status": status,
        "reason": reason,
        "identity": latest["identity"],
        "period_family": latest["period_family"],
        "period_type": latest["period_type"],
        "unit_family": latest["unit_family"],
        "currency": latest["currency"],
        "basis": latest["basis"],
        "total_points": identity_total,
        "selected_points": len(selected),
        "comparable_points": len(exact),
        "source_count": len(sources),
        "suppressed_points": suppressed,
        "suppressed_series": max(0, group_total - 1),
        "deduplicated_points": max(0, len(points) - len(selected)),
        "provenance_complete": all(
            point["source_id"] and point["source_url"] for point in selected
        ),
        "warnings": warnings,
    }
    return {
        "key": latest["_comparison_key"],
        "identity": latest["identity"],
        "metric": latest["metric"],
        "label": latest["label"],
        "period_family": latest["period_family"],
        "period_type": latest["period_type"],
        "basis": latest["basis"],
        "unit": latest["unit"],
        "unit_family": latest["unit_family"],
        "currency": latest["currency"],
        "latest_value": latest["value"],
        "previous_value": previous["value"] if previous else "",
        "latest_source_id": latest["source_id"],
        "latest_source_url": latest["source_url"],
        "previous_source_id": previous["source_id"] if previous else "",
        "previous_source_url": previous["source_url"] if previous else "",
        "change_direction": direction,
        "change_absolute": absolute,
        "change_percent": percent,
        "points": [_public_point(point) for point in selected[-8:]],
        "trend_points": [_public_point(point) for point in trend],
        "integrity": integrity,
        "_rank": min(point["_series_rank"] for point in selected),
        "_latest_effective": latest["_effective"],
        "_latest_published": latest["_published"],
    }


def project_company_metrics(
    raw_series: Sequence[Mapping[str, object]],
    *,
    max_series: int = 10,
) -> list[dict[str, Any]]:
    """Create one conservative, source-linked series per canonical KPI.

    Aliases merge only when explicitly registered. Periods, unit families,
    currencies and reported/calculated bases never mix. Unit scales may be
    converted for comparison without changing the disclosed display values.
    """

    flattened: list[dict[str, Any]] = []
    for series_rank, series in enumerate(raw_series):
        if not isinstance(series, Mapping):
            continue
        points = series.get("points") or []
        if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
            continue
        for point_rank, raw in enumerate(points):
            if isinstance(raw, Mapping):
                normalised = _point(raw, series, series_rank, point_rank)
                if normalised:
                    flattened.append(normalised)

    identities: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in flattened:
        identities[point["identity"]].append(point)

    output: list[dict[str, Any]] = []
    for identity_points in identities.values():
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for point in identity_points:
            grouped[point["_comparison_key"]].append(point)
        raw_groups = list(grouped.values())
        clean_groups = [_dedupe(group) for group in raw_groups]
        warnings = _warnings(clean_groups)
        candidates = [
            _series(group, len(identity_points), len(raw_groups), warnings)
            for group in raw_groups
        ]
        candidates = [
            item
            for item in candidates
            if item["points"]
            and item["points"][-1]["value"]
            and (
                item["points"][-1]["value_numeric"] is not None
                or item["points"][-1]["value_low"] is not None
                or item["points"][-1]["value_high"] is not None
            )
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda item: (
                item["_latest_effective"],
                item["_latest_published"],
                item["integrity"]["status"] == "comparable",
                item["integrity"]["selected_points"],
                -item["_rank"],
            ),
            reverse=True,
        )
        output.append(candidates[0])

    output.sort(
        key=lambda item: (
            item["_rank"],
            -item["_latest_published"].timestamp()
            if item["_latest_published"].year != datetime.min.year
            else 0.0,
        )
    )
    return [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in output[: max(0, max_series)]
    ]
