"""Conservative source context for copied financial tables, without an LLM.

Only explicit year columns, units and row cells are used. Unknown/irregular tables
remain ordinary source text, never inferred figures. Offsets always refer to the
original paste, including the common one-cell-per-line copy format.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
import re
from analyst.paste_quantities import Quantity, quantities, equal_at_display_precision

MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE = re.compile(rf'\b(\d{{1,2}})\s+({MONTH})\s+(20\d{{2}})\b', re.I)
YEAR = re.compile(r'\b20\d{2}\b')
CELL = re.compile(r'^(?:[+−-]?[£$€]?\(?\d[\d,]*(?:\.\d+)?\)?\s*(?:%|bps|p|m|k|bn)?|[–—-])$', re.I)
FINANCIAL = re.compile(r'revenue|sales|profit|loss|cash|debt|dividend|eps|earnings|margin|expense|income|asset|liabilit', re.I)
HEADER = re.compile(r"£\s*(?:m\b|million\b|['’]?000\b)", re.I)

@dataclass(frozen=True)
class Row:
    label: str
    values: tuple[str, ...]
    years: tuple[str, ...]
    unit: str
    start: int
    end: int
    header_start: int
    header_end: int

    def quantity(self, index: int) -> Quantity | None:
        cell = self.values[index].strip()
        if cell in {'-', '–', '—'}: return None  # blank is not reported zero
        negative = cell.startswith('(') and ')' in cell
        cell = cell.replace('(', '').replace(')', '')
        if negative: cell = '-' + cell
        # An explicit row-specific per-share/percent unit overrides £m columns.
        if not re.search(r'%|bps|p\b|£|\$|€|[mk]\b', cell, re.I):
            if re.search(r'\(\s*%\s*\)|margin', self.label, re.I): cell += '%'
            elif re.search(r'\(\s*p\s*\)|per share|\bEPS\b', self.label, re.I): cell += 'p'
            elif self.unit: cell = '£' + cell + self.unit
        found = quantities(cell)
        return found[0] if len(found) == 1 else None


def _tokens(source: str):
    tokens = []
    for line in re.finditer(r'[^\n]+', source):
        for part in re.finditer(r'[^\t]+', line[0]):
            value = part[0].strip()
            if value:
                start = line.start() + part.start() + len(part[0]) - len(part[0].lstrip())
                tokens.append((value, start, start + len(value)))
    return tokens


def table_rows(source: str) -> tuple[Row, ...]:
    tokens = _tokens(source)
    rows = []
    i = 0
    while i < len(tokens):
        # Explicit isolated year columns, optionally carrying their currency unit.
        if not re.fullmatch(r"20\d{2}(?:\s+£\s*(?:m|['’]?000))?", tokens[i][0], re.I):
            i += 1; continue
        h = i
        years, unit = [], ''
        while i < len(tokens) and i-h < 10:
            token = tokens[i][0]
            if re.fullmatch(r"20\d{2}(?:\s+£\s*(?:m|['’]?000))?", token, re.I):
                years.append(YEAR.search(token)[0])
            elif not re.fullmatch(r"£\s*(?:m|['’]?000)|change|notes?|%", token, re.I): break
            m = HEADER.search(token)
            if m: unit = 'k' if '000' in m[0] else 'm'
            i += 1
        if len(years) != 2 or len(set(years)) != 2:
            i = h+1; continue
        if not unit and h and HEADER.fullmatch(tokens[h-1][0]):
            unit = 'k' if '000' in tokens[h-1][0] else 'm'
            h -= 1
        has_change = any(t[0].lower() in {'change', '%'} for t in tokens[h:i])
        hend = tokens[i-1][2]
        block = []
        while i < len(tokens):
            label, start, end = tokens[i]
            if len(label) > 95 or CELL.fullmatch(label) or not FINANCIAL.search(label): break
            i += 1
            cells = []
            while i < len(tokens) and CELL.fullmatch(tokens[i][0]) and len(cells) < 5:
                cells.append(tokens[i][0]); end = tokens[i][2]; i += 1
            if len(cells) != (3 if has_change else 2): break
            # Three columns = two years and disclosed change; never infer a note column.
            block.append(Row(label, tuple(cells[:2]), tuple(years), unit, start, end, tokens[h][1], hend))
        if len(block) >= 2: rows.extend(block)
        i = max(i, h+1)
    return tuple(rows)


def metric_key(label: str) -> str | None:
    label = label.lower()
    adjusted = bool(re.search(r'\badj(?:usted|\.)?\b', label))
    if re.search(r'\bpbt\b|profit before tax', label): return 'adjusted_pbt' if adjusted else 'pbt'
    if re.search(r'operating profit', label): return 'adjusted_operating_profit' if adjusted else 'operating_profit'
    if re.search(r'net bank cash', label): return 'net_bank_cash'
    if re.search(r'net cash', label): return 'net_cash'
    if re.search(r'net (?:bank )?debt', label): return 'net_debt'
    if re.search(r'cash (?:and cash equivalents|balance)|^cash$', label): return 'cash'
    if 'dividend' in label and not re.search(r'yield|cover', label): return 'dividend'
    if re.search(r'^\s*(?:total\s+|group\s+)?revenue\s*[*¹²³]?\s*$', label): return 'revenue'
    if 'basic eps' in label or 'basic earnings per share' in label: return 'adjusted_eps' if adjusted else 'eps'
    return None


def reporting_context(source: str) -> tuple[int, int] | None:
    # Report date, not publication date. Only the opening statement of period.
    m = re.search(rf'\b(?:year|six months|half[- ]year)\s+(?:ended|to)\s+\d{{1,2}}\s+{MONTH}\s+20\d{{2}}\b', source[:4000], re.I)
    return (m.start(), m.end()) if m else None


def date_key(text: str):
    m = DATE.search(text)
    return (m[1].lstrip('0'), m[2][:3].lower(), m[3]) if m else None


def table_metric_check(metric, source: str, rows: tuple[Row, ...]) -> tuple[str, ...]:
    """Reject clear label/year/column mismatches, without guessing opaque layouts."""
    key = metric_key(metric.label)
    periods = YEAR.findall(re.sub(r'\bFY\s?(\d{2})\b', r'20\1', metric.period, flags=re.I))
    if key is None or len(set(periods)) != 1: return ()
    relevant = [r for r in rows if metric_key(r.label) == key and periods[0] in r.years]
    if not relevant: return ()
    display = quantities(metric.value)
    if len(display) != 1: return ()
    candidates = [r.quantity(r.years.index(periods[0])) for r in relevant]
    candidates = [c for c in candidates if c is not None]
    if not candidates: return ()
    return () if any(equal_at_display_precision(display[0], c) for c in candidates) else ('TABLE_PERIOD_VALUE_MISMATCH',)


def metric_reporting_quote(metric, source: str, rows: tuple[Row, ...]) -> tuple[int,int] | None:
    """Bind an exact report-end date to an explicit year-column metric.

    This supplies missing header context, not an invented date or a global licence
    to cite unrelated numbers. Dates not equal to the report end are never added.
    """
    span = reporting_context(source)
    if span is None or date_key(metric.period) is None: return None
    if date_key(metric.period) != date_key(source[span[0]:span[1]]): return None
    key = metric_key(metric.label)
    year = date_key(metric.period)[2]
    if key and any(metric_key(r.label) == key and year in r.years for r in rows): return span
    return None


def table_hints(source: str, catalog) -> list[dict]:
    """Small mechanical row/header map; all cells remain verbatim source values."""
    result = []
    for row in table_rows(source):
        if metric_key(row.label) is None: continue
        row_text = source[row.start:row.end]
        header_text = source[row.header_start:row.header_end]
        row_refs = [c.id for c in catalog.values() if row_text in c.quote]
        header_refs = [c.id for c in catalog.values() if header_text in c.quote]
        if not row_refs or not header_refs: continue
        result.append({'label': row.label, 'years': row.years, 'cells': row.values,
                       'unit': '£000' if row.unit == 'k' else '£m' if row.unit == 'm' else '',
                       'evidence': list(dict.fromkeys(header_refs[:1] + row_refs[:1]))})
        if len(result) == 8: break
    return result
