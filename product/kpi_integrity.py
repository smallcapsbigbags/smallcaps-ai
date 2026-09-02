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
    instant_hint: bool = False


@dataclass(frozen=True, slots=True)
class PeriodProfile:
    family: str
    period_type: PeriodType
    period_end: str
    year: int | None
    sort_date: datetime | None


@dataclass(frozen=True, slots=True)
class UnitProfile:
    family: str
    canonical_unit: str
    currency: str
    scale: float


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normalise(value: object) -> str:
    text = _clean(value).lower().replace("&", " and ")
    text = text.replace("£", " gbp ").replace("$", " usd ").replace("€", " eur ")
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", text).split())


def _slug(value: object) -> str:
    return "-".join(_normalise(value).replace("%", " percent ").split())


def _basis(value: object) -> str:
    return _normalise(value or "reported").replace(" ", "-") or "reported"


def _number(value: object) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        raw = _clean(value)
        if not raw:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _date(value: object) -> date | None:
    raw = _clean(value)
    if not raw:
        return None

    match = re.search(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b", raw)
    if match:
        try:
            return date.fromisoformat(match.group(0))
        except ValueError:
            pass

    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-]((?:19|20)\d{2})\b", raw)
    if match:
        day, month, year = (int(item) for item in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            pass

    cleaned = re.sub(
        r"(?i)\b(?:as\s+at|as\s+of|at|for\s+the\s+(?:year|period)\s+ended|year\s+ended|period\s+ended|ended)\b",
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


def _expand_year(raw: str) -> int | None:
    try:
        year = int(raw)
    except ValueError:
        return None
    if year < 100:
        return 2000 + year if year <= 69 else 1900 + year
    return year if 1900 <= year <= 2200 else None


def _year(normalised: str) -> int | None:
    match = re.search(r"\bfy\s*(\d{2,4})\b", normalised)
    if match:
        return _expand_year(match.group(1))
    years = re.findall(r"\b(?:19|20)\d{2}\b", normalised)
    return int(years[-1]) if years else None


def _sort_date(end: date | None, year: int | None, family: str) -> datetime | None:
    if end:
        return datetime(end.year, end.month, end.day, tzinfo=timezone.utc)
    if year is None:
        return None
    month_day = {
        "Q1": (3, 31),
        "Q2": (6, 30),
        "Q3": (9, 30),
        "Q4": (12, 31),
        "H1": (6, 30),
        "H2": (12, 31),
        "HY": (6, 30),
        "3M": (3, 31),
        "6M": (6, 30),
        "9M": (9, 30),
        "12M": (12, 31),
    }.get(family, (12, 31))
    return datetime(year, month_day[0], month_day[1], tzinfo=timezone.utc)


def _strip_metric_metadata(value: object) -> str:
    raw = _clean(value)
    if not raw:
        return ""

    allowed_unit_parentheticals = {
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
        "percentage",
        "pp",
        "bps",
        "x",
        "shares",
        "million shares",
    }

    def remove_unit(match: re.Match[str]) -> str:
        return " " if _normalise(match.group(1)) in allowed_unit_parentheticals else match.group(0)

    raw = re.sub(r"\(([^()]*)\)", remove_unit, raw)
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


_IDENTITIES: tuple[tuple[MetricIdentity, tuple[str, ...]], ...] = (
    (MetricIdentity("net-debt", "net debt", "Net debt", True), ("net debt", "net borrowings", "net financial debt")),
    (MetricIdentity("net-cash", "net cash", "Net cash", True), ("net cash", "net funds")),
    (MetricIdentity("cash", "cash", "Cash", True), ("cash", "cash balance", "cash and cash equivalents")),
    (MetricIdentity("liquidity", "liquidity", "Liquidity", True), ("liquidity", "available liquidity")),
    (MetricIdentity("revenue", "revenue", "Revenue"), ("revenue", "group revenue", "turnover")),
    (MetricIdentity("recurring-revenue", "recurring revenue", "Recurring revenue"), ("recurring revenue",)),
    (
        MetricIdentity("annual-recurring-revenue", "annual recurring revenue", "Annual recurring revenue", True),
        ("annual recurring revenue", "arr"),
    ),
    (MetricIdentity("net-fee-income", "net fee income", "Net fee income"), ("net fee income", "nfi")),
    (MetricIdentity("ebitda", "ebitda", "EBITDA"), ("ebitda", "reported ebitda")),
    (MetricIdentity("adjusted-ebitda", "adjusted ebitda", "Adjusted EBITDA"), ("adjusted ebitda",)),
    (MetricIdentity("ebitda-margin", "ebitda margin", "EBITDA margin"), ("ebitda margin",)),
    (
        MetricIdentity("adjusted-ebitda-margin", "adjusted ebitda margin", "Adjusted EBITDA margin"),
        ("adjusted ebitda margin",),
    ),
    (
        MetricIdentity("profit-before-tax", "profit before tax", "Profit before tax"),
        ("profit before tax", "pbt", "statutory profit before tax"),
    ),
    (
        MetricIdentity("adjusted-profit-before-tax", "adjusted profit before tax", "Adjusted profit before tax"),
        ("adjusted profit before tax", "adjusted pbt"),
    ),
    (MetricIdentity("operating-profit", "operating profit", "Operating profit"), ("operating profit",)),
    (MetricIdentity("gross-profit", "gross profit", "Gross profit"), ("gross profit",)),
    (MetricIdentity("gross-margin", "gross margin", "Gross margin"), ("gross margin",)),
    (MetricIdentity("operating-margin", "operating margin", "Operating margin"), ("operating margin",)),
    (MetricIdentity("free-cash-flow", "free cash flow", "Free cash flow"), ("free cash flow", "fcf")),
    (
        MetricIdentity("operating-cash-flow", "operating cash flow", "Operating cash flow"),
        ("operating cash flow", "cash generated from operations"),
    ),
    (MetricIdentity("cash-conversion", "cash conversion", "Cash conversion"), ("cash conversion",)),
    (MetricIdentity("order-book", "order book", "Order book", True), ("order book",)),
    (MetricIdentity("backlog", "backlog", "Backlog", True), ("backlog",)),
    (MetricIdentity("loan-book", "loan book", "Loan book", True), ("loan book",)),
    (
        MetricIdentity("assets-under-management", "assets under management", "Assets under management", True),
        ("assets under management", "aum"),
    ),
    (MetricIdentity("net-asset-value", "net asset value", "Net asset value", True), ("net asset value", "nav")),
    (MetricIdentity("inventory", "inventory", "Inventory", True), ("inventory",)),
    (MetricIdentity("loan-to-value", "loan to value", "Loan to value", True), ("loan to value", "ltv")),
    (MetricIdentity("basic-eps", "basic eps", "Basic EPS"), ("basic eps", "basic earnings per share")),
    (MetricIdentity("adjusted-eps", "adjusted eps", "Adjusted EPS"), ("adjusted eps", "adjusted earnings per share")),
    (
        MetricIdentity("dividend-per-share", "dividend per share", "Dividend per share"),
        ("dividend per share", "dps"),
    ),
    (MetricIdentity("shares-in-issue", "shares in issue", "Shares in issue", True), ("shares in issue", "ordinary shares in issue")),
    (
        MetricIdentity("total-voting-rights", "total voting rights", "Total voting rights", True),
        ("total voting rights", "voting rights"),
    ),
    (MetricIdentity("completions", "completions", "Completions"), ("completions",)),
    (MetricIdentity("production", "production", "Production"), ("production",)),
    (MetricIdentity("all-in-sustaining-cost", "all in sustaining cost", "AISC"), ("all in sustaining cost", "aisc")),
    (MetricIdentity("recovery", "recovery", "Recovery"), ("recovery", "recovery rate")),
)

_ALIAS_TO_IDENTITY = {
    _normalise(alias): identity
    for identity, aliases in _IDENTITIES
    for alias in aliases
}


def metric_identity(metric: object, label: object = "") -> MetricIdentity:
    source = _strip_metric_metadata(metric) or _strip_metric_metadata(label)
    normalised = _normalise(source)
    known = _ALIAS_TO_IDENTITY.get(normalised)
    if known:
        return known

    key = _slug(normalised) or "metric"
    display = _strip_metric_metadata(label) or _strip_metric_metadata(metric) or "Metric"
    instant_hint = any(
        term in normalised
        for term in (
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
    return MetricIdentity(key, normalised or "metric", display, instant_hint)


def period_profile(period: object, as_of_date: object = "", *, instant_hint: bool = False) -> PeriodProfile:
    raw = _clean(period)
    normalised = _normalise(raw)
    parsed_end = _date(as_of_date) or _date(raw)
    year = parsed_end.year if parsed_end else _year(normalised)
    family = "UNKNOWN"
    period_type: PeriodType = "unknown"

    if as_of_date or re.search(r"\b(?:point in time|instant|as at|as of)\b", normalised):
        family, period_type = "POINT", "instant"
    else:
        weeks = re.search(r"\b(5[23])\s+weeks?\b", normalised)
        half = re.search(r"\bh([12])\b", normalised)
        quarter = re.search(r"\bq([1-4])\b", normalised)
        months = re.search(r"\b(\d{1,2})\s+months?\b", normalised)

        if weeks:
            family, period_type = f"FY{weeks.group(1)}W", "duration"
        elif half or "first half" in normalised or "second half" in normalised:
            if "second half" in normalised or (half and half.group(1) == "2"):
                family = "H2"
            else:
                family = "H1"
            period_type = "duration"
        elif quarter:
            family, period_type = f"Q{quarter.group(1)}", "duration"
        elif (
            re.search(r"\bfy\s*\d{2,4}\b", normalised)
            or "full year" in normalised
            or "year ended" in normalised
            or "twelve months" in normalised
        ):
            family, period_type = "FY", "duration"
        elif "half year" in normalised or "half-year" in raw.lower():
            family, period_type = "HY", "duration"
        elif months:
            family, period_type = f"{int(months.group(1))}M", "duration"
        elif "three months" in normalised:
            family, period_type = "3M", "duration"
        elif "six months" in normalised:
            family, period_type = "6M", "duration"
        elif "nine months" in normalised:
            family, period_type = "9M", "duration"
        elif "year to date" in normalised or re.search(r"\bytd\b", normalised):
            family, period_type = "YTD", "duration"
        elif re.fullmatch(r"(?:fy\s*)?(?:20\d{2}|19\d{2}|\d{2})", normalised):
            family, period_type = "CY", "duration"
        elif any(
            term in normalised
            for term in ("transaction", "current authority", "possible offer", "contract", "programme", "award")
        ):
            family, period_type = f"EVENT:{_slug(normalised) or 'event'}", "event"
        elif instant_hint and normalised in {"", "current", "latest"}:
            family, period_type = "POINT", "instant"

    return PeriodProfile(
        family=family,
        period_type=period_type,
        period_end=parsed_end.isoformat() if parsed_end else "",
        year=year,
        sort_date=_sort_date(parsed_end, year, family),
    )


_CURRENCY_ALIASES = {
    "gbp": "GBP",
    "sterling": "GBP",
    "usd": "USD",
    "us dollar": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "cad": "CAD",
    "aud": "AUD",
    "zar": "ZAR",
}


def _currency(currency: object, unit: object, value: object) -> str:
    raw = _clean(currency)
    if raw == "GBp":
        return "GBp"
    lowered = raw.lower()
    if lowered in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[lowered]
    if re.fullmatch(r"[A-Za-z]{3}", raw):
        return raw.upper()

    combined = f"{_clean(unit)} {_clean(value)}"
    for symbol, code in (("£", "GBP"), ("$", "USD"), ("€", "EUR")):
        if symbol in combined:
            return code
    normalised = _normalise(combined)
    for alias, code in _CURRENCY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalised):
            return code
    return ""


def unit_profile(unit: object, currency: object, value: object, *, identity: MetricIdentity) -> UnitProfile:
    raw_unit = _clean(unit)
    raw_value = _clean(value)
    normalised = _normalise(f"{raw_unit} {raw_value}")
    unit_normalised = _normalise(raw_unit)
    canonical_currency = _currency(currency, raw_unit, raw_value)

    if (
        re.search(r"\b(?:billion|bn)\b", normalised)
        or unit_normalised in {"gbp bn", "usd bn", "eur bn"}
        or re.search(r"(?i)(?:£|\$|€)?\s*[-+]?\d[\d,.]*\s*bn\b", raw_value)
    ):
        scale = 1_000_000_000.0
    elif (
        re.search(r"\b(?:million|mn)\b", normalised)
        or re.search(r"(?i)(?:£|\$|€)?\s*[-+]?\d[\d,.]*\s*m\b", raw_value)
        or unit_normalised in {"m", "gbp m", "usd m", "eur m"}
    ):
        scale = 1_000_000.0
    elif (
        re.search(r"\b(?:thousand|000)\b", normalised)
        or re.search(r"(?i)(?:£|\$|€)?\s*[-+]?\d[\d,.]*\s*k\b", raw_value)
        or unit_normalised in {"k", "gbp k", "usd k", "eur k"}
    ):
        scale = 1_000.0
    else:
        scale = 1.0

    if re.search(r"\b(?:basis points?|bps)\b", normalised):
        return UnitProfile("percentage-point", "pp", "", 0.01)
    if re.search(r"\b(?:percentage points?|pp)\b", normalised) or re.search(
        r"(?i)[-+]?\d[\d,.]*\s*pp\b", raw_value
    ):
        return UnitProfile("percentage-point", "pp", "", 1.0)
    if "%" in raw_unit or "%" in raw_value or re.search(r"\b(?:percent|percentage)\b", normalised):
        return UnitProfile("percent", "%", "", 1.0)
    if re.search(r"(?i)[-+]?\d[\d,.]*\s*x\b", raw_value) or unit_normalised in {"x", "times", "multiple"}:
        return UnitProfile("multiple", "x", "", 1.0)
    if re.search(r"\bshares?\b", normalised):
        return UnitProfile("shares", "shares", "", scale)
    if canonical_currency:
        return UnitProfile("currency", canonical_currency, canonical_currency, scale)
    if re.search(r"\bdays?\b", normalised):
        return UnitProfile("days", "days", "", scale)
    if re.search(r"\b(?:tonnes?|tons?)\b", normalised):
        return UnitProfile("tonnes", "tonnes", "", scale)
    if re.search(r"\bounces?\b", normalised):
        return UnitProfile("ounces", "ounces", "", scale)
    if re.search(r"\b(?:barrels?|boe|boepd)\b", normalised):
        family = "boepd" if "boepd" in normalised else "barrels"
        return UnitProfile(family, family, "", scale)
    if re.search(r"\b(?:units?|homes?|customers?|employees?|headcount)\b", normalised):
        return UnitProfile("count", "count", "", scale)
    if raw_unit:
        return UnitProfile(_slug(raw_unit) or "number", raw_unit, "", scale)
    return UnitProfile("number", "", "", scale)


def _exact(point: Mapping[str, object]) -> float | None:
    numeric = _number(point.get("value_numeric"))
    if numeric is not None:
        return numeric
    low = _number(point.get("value_low"))
    high = _number(point.get("value_high"))
    if low is not None and high is not None and math.isclose(low, high, rel_tol=0.0, abs_tol=1e-12):
        return low
    return None


def _numeric_kind(point: Mapping[str, object]) -> str:
    if _exact(point) is not None:
        return "exact"
    if _number(point.get("value_low")) is not None or _number(point.get("value_high")) is not None:
        return "range"
    return "non-numeric"


def _normalised_point(
    raw: Mapping[str, object],
    series: Mapping[str, object],
    *,
    series_rank: int,
    point_rank: int,
) -> dict[str, Any] | None:
    metric = _clean(raw.get("metric") or series.get("metric") or raw.get("label") or series.get("label"))
    label = _clean(raw.get("label") or series.get("label") or metric)
    value = _clean(raw.get("value"))
    if not metric or not value or value.lower() == "not disclosed":
        return None

    identity = metric_identity(metric, label)
    period = _clean(raw.get("period"))
    as_of_date = _clean(raw.get("as_of_date"))
    period_meta = period_profile(period, as_of_date, instant_hint=identity.instant_hint)
    unit_meta = unit_profile(
        raw.get("unit") or series.get("unit"),
        raw.get("currency") or series.get("currency"),
        value,
        identity=identity,
    )
    basis = _basis(raw.get("basis") or series.get("basis"))
    numeric = _exact(raw)
    comparable_numeric = numeric * unit_meta.scale if numeric is not None else None
    published_dt = _datetime(raw.get("published_at"))
    published_at = published_dt.isoformat() if published_dt.year != datetime.min.year else _clean(raw.get("published_at"))
    source_id = _clean(raw.get("source_id"))
    source_url = _clean(raw.get("source_url"))

    period_token = (
        period_meta.period_end
        or (f"{period_meta.family}:{period_meta.year}" if period_meta.year is not None else "")
        or _normalise(period)
    )
    if period_meta.period_type == "instant" and not period_token:
        period_token = published_dt.date().isoformat() if published_dt.year != datetime.min.year else source_id
    if period_meta.period_type in {"event", "unknown"} and not period_token:
        period_token = source_id or f"{series_rank}:{point_rank}"

    effective_dt = period_meta.sort_date
    if effective_dt is None and published_dt.year != datetime.min.year:
        effective_dt = published_dt

    return {
        "source_id": source_id,
        "published_at": published_at,
        "title": _clean(raw.get("title")),
        "source_url": source_url,
        "label": identity.label,
        "metric": identity.metric,
        "identity": identity.key,
        "period": period,
        "period_family": period_meta.family,
        "period_type": period_meta.period_type,
        "period_end": period_meta.period_end,
        "value": value,
        "value_numeric": _number(raw.get("value_numeric")),
        "value_low": _number(raw.get("value_low")),
        "value_high": _number(raw.get("value_high")),
        "unit": _clean(raw.get("unit") or series.get("unit")),
        "unit_family": unit_meta.family,
        "unit_scale": unit_meta.scale,
        "comparable_value_numeric": comparable_numeric,
        "currency": unit_meta.currency,
        "as_of_date": as_of_date,
        "basis": basis,
        "note": _clean(raw.get("note")),
        "_comparison_key": "|".join(
            (identity.key, period_meta.family, unit_meta.family, unit_meta.currency or "-", basis)
        ),
        "_period_token": period_token,
        "_numeric_kind": _numeric_kind(raw),
        "_effective_dt": effective_dt or datetime.min.replace(tzinfo=timezone.utc),
        "_published_dt": published_dt,
        "_series_rank": series_rank,
        "_point_rank": point_rank,
    }


def _dedupe(points: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_slot: dict[str, dict[str, Any]] = {}
    for point in points:
        slot = point["_period_token"] or point["source_id"] or str(point["_point_rank"])
        existing = by_slot.get(slot)
        if existing is None or (
            point["_published_dt"],
            point["_series_rank"],
            point["_point_rank"],
        ) >= (
            existing["_published_dt"],
            existing["_series_rank"],
            existing["_point_rank"],
        ):
            by_slot[slot] = point
    return sorted(
        by_slot.values(),
        key=lambda point: (
            point["_effective_dt"],
            point["_published_dt"],
            point["_series_rank"],
            point["_point_rank"],
        ),
    )


def _warnings(groups: Sequence[Sequence[dict[str, Any]]]) -> list[str]:
    period_families = {group[-1]["period_family"] for group in groups if group}
    unit_families = {group[-1]["unit_family"] for group in groups if group}
    currencies = {group[-1]["currency"] for group in groups if group}
    bases = {group[-1]["basis"] for group in groups if group}
    output: list[str] = []
    if len(period_families) > 1:
        output.append("INCOMPATIBLE_PERIOD")
    if len(unit_families) > 1:
        output.append("INCOMPATIBLE_UNIT")
    if len(currencies) > 1:
        output.append("INCOMPATIBLE_CURRENCY")
    if len(bases) > 1:
        output.append("INCOMPATIBLE_BASIS")
    return output


def _status(
    points: Sequence[dict[str, Any]],
    exact_points: Sequence[dict[str, Any]],
) -> tuple[TrendStatus, str]:
    latest = points[-1]
    if latest["_numeric_kind"] == "range":
        return "range-only", "The latest disclosure is a range, so no point trend is drawn."
    if latest["_numeric_kind"] == "non-numeric":
        return "non-numeric", "The latest disclosure is not an exact number."
    if latest["period_type"] in {"event", "unknown"}:
        return "insufficient-period", "Period metadata is not precise enough for a like-for-like trend."
    if any(not point["source_id"] or not point["source_url"] for point in exact_points):
        return "missing-provenance", "A trend is withheld because an observation lacks complete source provenance."
    if len(exact_points) < 2:
        return "single-point", "Only one comparable exact observation is available."
    return "comparable", "Metric identity, period, unit, currency and basis are like for like."


def _public_point(point: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: point[key]
        for key in (
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
    }


def _candidate(
    raw_points: Sequence[dict[str, Any]],
    *,
    identity_point_count: int,
    group_count: int,
    warnings: list[str],
) -> dict[str, Any]:
    points = _dedupe(raw_points)
    latest = points[-1]
    exact_points = [
        point
        for point in points
        if point["comparable_value_numeric"] is not None
        and point["period_type"] not in {"event", "unknown"}
    ]
    status, reason = _status(points, exact_points)
    trend_points = exact_points[-8:] if status == "comparable" else []
    previous = trend_points[-2] if status == "comparable" else None

    change_absolute: float | None = None
    change_percent: float | None = None
    change_direction = "unclear"
    if previous:
        current_base = trend_points[-1]["comparable_value_numeric"]
        previous_base = previous["comparable_value_numeric"]
        if current_base is not None and previous_base is not None:
            delta = current_base - previous_base
            change_absolute = delta / (latest["unit_scale"] or 1.0)
            tolerance = max(abs(previous_base), 1.0) * 1e-9
            if abs(delta) <= tolerance:
                change_direction = "flat"
            else:
                change_direction = "up" if delta > 0 else "down"
            if previous_base:
                change_percent = delta / abs(previous_base) * 100.0

    suppressed_points = max(0, identity_point_count - len(raw_points))
    if suppressed_points:
        verb = "remains" if suppressed_points == 1 else "remain"
        reason += (
            f" {suppressed_points} observation"
            f"{'s' if suppressed_points != 1 else ''} from a different period, unit, "
            f"currency or basis {verb} separate."
        )

    source_ids = {point["source_id"] for point in points if point["source_id"]}
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
        "total_points": identity_point_count,
        "selected_points": len(points),
        "comparable_points": len(exact_points),
        "source_count": len(source_ids),
        "suppressed_points": suppressed_points,
        "suppressed_series": max(0, group_count - 1),
        "deduplicated_points": max(0, len(raw_points) - len(points)),
        "provenance_complete": all(point["source_id"] and point["source_url"] for point in points),
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
        "change_direction": change_direction,
        "change_absolute": change_absolute,
        "change_percent": change_percent,
        "points": [_public_point(point) for point in points[-8:]],
        "trend_points": [_public_point(point) for point in trend_points],
        "integrity": integrity,
        "_rank": min(point["_series_rank"] for point in points),
        "_latest_effective": latest["_effective_dt"],
        "_latest_published": latest["_published_dt"],
    }


def project_company_metrics(
    raw_series: Sequence[Mapping[str, object]],
    *,
    max_series: int = 10,
) -> list[dict[str, Any]]:
    """Build a source-linked public KPI record without mixing unlike observations.

    Raw disclosures are preserved. The projection merges only registered aliases,
    separates incompatible periods/units/currencies/bases, converts unit scale for
    comparison only, and exposes a trend only when at least two exact observations
    have complete provenance and genuinely like-for-like metadata.
    """

    flattened: list[dict[str, Any]] = []
    for series_rank, series in enumerate(raw_series):
        if not isinstance(series, Mapping):
            continue
        points = series.get("points") or []
        if not isinstance(points, Sequence) or isinstance(points, (str, bytes)):
            continue
        for point_rank, raw in enumerate(points):
            if not isinstance(raw, Mapping):
                continue
            point = _normalised_point(
                raw,
                series,
                series_rank=series_rank,
                point_rank=point_rank,
            )
            if point:
                flattened.append(point)

    by_identity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in flattened:
        by_identity[point["identity"]].append(point)

    selected: list[dict[str, Any]] = []
    for identity_points in by_identity.values():
        by_comparison: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for point in identity_points:
            by_comparison[point["_comparison_key"]].append(point)

        clean_groups = [_dedupe(points) for points in by_comparison.values() if points]
        warnings = _warnings(clean_groups)
        candidates = [
            _candidate(
                points,
                identity_point_count=len(identity_points),
                group_count=len(by_comparison),
                warnings=warnings,
            )
            for points in by_comparison.values()
            if points
        ]
        displayable = [
            candidate
            for candidate in candidates
            if candidate["points"]
            and candidate["points"][-1]["value"]
            and (
                candidate["points"][-1]["value_numeric"] is not None
                or candidate["points"][-1]["value_low"] is not None
                or candidate["points"][-1]["value_high"] is not None
            )
        ]
        if not displayable:
            continue

        displayable.sort(
            key=lambda candidate: (
                candidate["_latest_effective"],
                candidate["_latest_published"],
                candidate["integrity"]["status"] == "comparable",
                candidate["integrity"]["selected_points"],
                -candidate["_rank"],
            ),
            reverse=True,
        )
        selected.append(displayable[0])

    selected.sort(
        key=lambda candidate: (
            candidate["_rank"],
            -candidate["_latest_published"].timestamp()
            if candidate["_latest_published"].year != datetime.min.year
            else 0.0,
        )
    )
    return [
        {key: value for key, value in candidate.items() if not key.startswith("_")}
        for candidate in selected[: max(0, max_series)]
    ]
