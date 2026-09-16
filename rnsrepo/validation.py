"""Focused checks on displayed claims, not an equity-research publication gate.

Matching numbers/quotations does not establish causal or semantic correctness. Keep
that limitation explicit; never label the original user paste independently verified.
"""
from __future__ import annotations
import re
from .schema import CardDraft, CardError
from .sections import Selection
from .financial_context import table_rows, table_metric_check, metric_reporting_quote, DATE, date_key
from .source_context import payment_sentences, CORRECTION
from analyst.paste_quantities import supported_numbers, bound_preserved, quantities, source_quantities, equal_at_display_precision

EXPECTED = re.compile(r"\bexpect\w*|\bforecast\w*|\btarget\w*|\banticipat\w*|\bguidance\b", re.I)
PROPOSED = re.compile(r"\bpropos\w*|\bintend\w*|\brecommend\w*|\bplan(?:s|ned)?\b", re.I)
CONDITION = re.compile(r"subject to|depend\w*|conditional|following successful|upon successful|contingent|no certainty|not certain|remain required|uncertain|not (?:confirmed|committed)|illustrative|under discussion", re.I)
POST = re.compile(r"(?:post|after|since)[- ](?:the )?(?:year|period)[- ]end|subsequent", re.I)
PAYMENT = re.compile(r"paid|payment|consideration", re.I)


UNCERTAINTY = re.compile(r"material(?:\s+going[-‑ ]concern)?\s+uncertaint(?:y|ies)", re.I)

def is_balance(label: str) -> bool:
    return bool(re.search(r"cash|debt", label, re.I) and not re.search(
        r"consideration|payment|proceeds|receipts?|element|cash[- ]?flow|cost|facility|financing", label, re.I))


def metric_evidence(metric, quotes: list[str]) -> str:
    """Ignore separate header/date references when checking a value's conditions.

    Full quotations remain the numeric evidence. Never trim a condition out of an
    excerpt containing the actual value. A generic condition-only reference is also
    retained. This avoids applying another metric's forecast to an actual result.
    """
    values = quantities(_numeric_text(metric.value))
    chosen = []
    for quote in quotes:
        qs = source_quantities(_numeric_text(quote))
        matching = any(equal_at_display_precision(v, q) for v in values for q in qs)
        condition_only = CONDITION.search(quote) and not qs
        if matching:
            sentences = re.split(r'(?<=[.!?])\s+|\n\s*\n', quote)
            relevant = [s for s in sentences if any(
                equal_at_display_precision(v,q) for v in values
                for q in source_quantities(_numeric_text(s)))]
            # A separate condition-only sentence is not lost. Ambiguous table
            # context remains whole; numeric header units are not inferred here.
            relevant += [s for s in sentences if CONDITION.search(s) and not quantities(_numeric_text(s))]
            chosen.extend(relevant or [quote])
        elif condition_only: chosen.append(quote)
    return "\n".join(chosen) if chosen else "\n".join(quotes)


def _numeric_text(text: str) -> str:
    # Dates are validated atomically below. Canonicalise equivalent dotted/ISO
    # dates before comparing quantities; do not split 2026-09-01 into negatives.
    def date_alias(match):
        key = date_key(match[0])
        return ' '.join(key) if key else match[0]
    text = DATE.sub(date_alias, text)
    # A labelled share count can have issuer-defined adjectives between the
    # number and "shares". Keep the count unit; never confuse currency and shares.
    text = re.sub(r"(?<=\d)\s+(?:(?:new|ordinary|vendor|placing|retail|offer)\s+){1,4}(shares?\b)", r" \1", text, flags=re.I)
    text = re.sub(r"\bFY\s?(20\d{2})\b", r"\1", text, flags=re.I)
    text = re.sub(r"\b(?:a )?reduction of\s+(\d+(?:\.\d+)?\s*%)", r"-\1", text, flags=re.I)
    # Equivalent disclosed bounds and UK percentage notation. These aliases do
    # not remove a floor/ceiling or create a new derived percentage.
    text = re.sub(r"\b(?:no|not) less than\b", "at least", text, flags=re.I)
    text = re.sub(r"\b(?:no|not) more than\b", "at most", text, flags=re.I)
    text = re.sub(r"\bper\s+cent\.?", "%", text, flags=re.I)
    text = re.sub(r"\bc\.\s*(?=\d)", "approximately ", text, flags=re.I)
    text = re.sub(r"\b(?:below|less than|under)\s+(?=[£$€]?\d)", "<", text, flags=re.I)
    # Common RNS negative-currency notation with a superscript footnote marker.
    text = re.sub(r"([£$€])\((\d[\d,]*(?:\.\d+)?)\)[¹²³⁴⁵⁶⁷⁸⁹⁰]*(?:\s*(m|k|bn)\b)?", r"-\1\2\3", text, flags=re.I)
    text = re.sub(r"\((\d+(?:\.\d+)?)\)\s*(%|bps\b)", r"-\1\2", text, flags=re.I)
    text = re.sub(r"\b(?:down|decreased by|fell by)\s+(\d+(?:\.\d+)?\s*%)", r"-\1", text, flags=re.I)
    # Hyphenated numeric durations are the same quantity as their spaced source
    # form. This does not remove negative signs, change amounts or allow rounding.
    text = re.sub(r"(?<=\d)[-‐‑–](?=(?:months?|years?)\b)", " ", text, flags=re.I)
    # A fiscal-year display is an alias, not a new figure. Preserve all other digits.
    return re.sub(r"\bFY\s?(\d{2})\b", lambda m: "20" + m[1], text, flags=re.I)


def forecast_applies(visible: str, evidence: str) -> bool:
    """A forecast elsewhere in a citation does not turn an actual into a forecast.

    Require a matching displayed financial amount/duration in the forecast sentence.
    Production dates are matched too. "As expected" describes an actual outcome.
    """
    targets = quantities(_numeric_text(visible))
    targets = [q for q in targets if q.unit != 'number' or re.search(r'production|launch', visible, re.I)]
    for sentence in re.split(r'(?<=[.!?])\s+|\n', evidence):
        cleaned = re.sub(r'\bas expected\b', '', sentence, flags=re.I)
        if not EXPECTED.search(cleaned): continue
        values = source_quantities(_numeric_text(cleaned))
        if any(equal_at_display_precision(v, q) for v in targets for q in values): return True
    return False


def check_card(source: str, selection: Selection, card: CardDraft) -> dict:
    by_id = {p.id: p for p in selection.passages}
    anchors = []
    findings = []
    details = []
    current_field = 'card'
    def record(code):
        findings.append(code)
        details.append({'field': current_field, 'code': code})
    rows = table_rows(source)

    def support(refs, field: str) -> str:
        parts = []
        for ref in refs:
            passage = by_id.get(ref.passage_id)
            if passage is None:
                record("UNKNOWN_PASSAGE"); continue
            rx = r"\s+".join(re.escape(w) for w in ref.quote.split())
            match = re.search(rx, passage.text)
            if match is None:
                record("QUOTE_NOT_FOUND"); continue
            start, end = passage.start + match.start(), passage.start + match.end()
            quote = source[start:end]
            anchors.append({"field": field, "start": start, "end": end, "quote": quote})
            parts.append(quote)
        return "\n".join(parts)

    def check_numbers(visible: str, evidence: str, *, loss_value: str = "") -> None:
        evidence_dates = {date_key(m[0]) for m in DATE.finditer(evidence)}
        if any(date_key(m[0]) is None or date_key(m[0]) not in evidence_dates for m in DATE.finditer(visible)):
            record("UNSUPPORTED_DATE")
        numeric_evidence = _numeric_text(evidence)
        # Financial statements show losses in brackets. A tile explicitly labelled
        # "loss" may show that magnitude. This never permits a loss to become profit.
        if loss_value:
            target = quantities(_numeric_text(loss_value))
            if len(target) == 1 and target[0].amount >= 0:
                q = target[0]
                if any(c.unit == q.unit and c.amount < 0 and equal_at_display_precision(q, type(c)(-c.amount, c.unit, c.bound, c.precision)) for c in source_quantities(numeric_evidence)):
                    numeric_evidence += " " + loss_value
        if not supported_numbers(_numeric_text(visible), numeric_evidence):
            record("UNSUPPORTED_NUMBER")
        if not bound_preserved(_numeric_text(visible), numeric_evidence):
            record("BOUND_CHANGED")

    def check_commitments(visible: str, evidence: str) -> None:
        if re.search(r"\b(?:guaranteed|debt[- ]free)\b|contracted recurring", visible, re.I):
            if not re.search(r"\b(?:not|no|isn.t)\b.{0,35}(?:guaranteed|debt[- ]free|contracted)", visible, re.I):
                if not re.search(r"guaranteed|debt[- ]free|contracted recurring", evidence, re.I):
                    record("UNSUPPORTED_COMMITMENT")
        if re.search(r"net bank cash", evidence, re.I) and re.search(r"\bnet cash\b", visible, re.I):
            record("BANK_BASIS_LOST")
        if re.search(r"\b(?:today|currently|now)\b.{0,30}(?:cash|debt)|(?:cash|debt).{0,30}\btoday\b", visible, re.I):
            if re.search(r"year[- ]end|period[- ]end|\bat 31\b|\bat 30\b", evidence, re.I):
                record("BALANCE_DATE_CHANGED")

    visible_parts = []
    for name in ("headline", "supporting_sentence", "what_changed", "qualification"):
        current_field = name
        statement = getattr(card, name)
        if statement is None: continue
        if not statement.text.strip(): record("EMPTY_TEXT")
        evidence = support(statement.evidence, name)
        check_numbers(statement.text, evidence)
        check_commitments(statement.text, evidence)
        visible_parts.append(statement.text)
        # Forecast/proposal qualifications apply to a numerical claim, not every
        # generic description of an already awarded development programme.
        if quantities(statement.text):
            if re.search(r"revenue|production|profit|runway", statement.text, re.I) and forecast_applies(statement.text, evidence):
                if not (EXPECTED.search(statement.text) or CONDITION.search(statement.text)):
                    record("EXPECTED_QUALIFIER_LOST")
            if re.search(r"dividend|buyback", statement.text, re.I) and PROPOSED.search(evidence):
                if not PROPOSED.search(statement.text): record("PROPOSED_QUALIFIER_LOST")

    seen = set()
    for i, metric in enumerate(card.metrics):
        current_field = f"metrics.{i}"
        evidence = support(metric.evidence, current_field)
        # A table row and its report header are one piece of financial evidence,
        # even when a browser copy put them into different excerpts. The exact
        # date must match the opening report end, and the value must match that
        # row's year column. Do not add arbitrary document-wide numbers.
        for code in table_metric_check(metric, source, rows): record(code)
        date_span = metric_reporting_quote(metric, source, rows)
        if date_span is not None:
            start, end = date_span
            quote = source[start:end]
            evidence += "\n" + quote
            anchors.append({"field": f"metrics.{i}", "start": start, "end": end, "quote": quote})
        visible = " ".join((metric.label, metric.value, metric.period, metric.note))
        check_numbers(visible, evidence, loss_value=metric.value if re.search(r"\bloss\b", metric.label, re.I) else "")
        check_commitments(visible, evidence)
        visible_parts.append(visible)
        nil_price = (metric.value.strip().lower() == "nil" and re.search(r"price|cost", metric.label, re.I)
                     and re.search(r"\bnil\b", evidence, re.I))
        if not quantities(_numeric_text(metric.value)) and not nil_price: record("METRIC_NOT_NUMERICAL")
        identity = (metric.label.lower().strip(), metric.period.lower().strip())
        if identity in seen: record("DUPLICATE_METRIC")
        seen.add(identity)
        # Short quoted context must identify the metric, not merely contain its number.
        aliases = [(r"revenue|sales", r"revenue|sales"), (r"dividend", r"dividend"),
            (r"cash|debt", r"cash|debt"), (r"pbt|profit", r"pbt|profit"),
            (r"production", r"production"), (r"develop", r"develop"),
            (r"issue price|placing price", r"issue price|placing price|per share|pence|\bp\b")]
        for label_rx, evidence_rx in aliases:
            if re.search(label_rx, metric.label, re.I) and not re.search(evidence_rx, evidence, re.I):
                record("METRIC_BASIS_MISSING")
        if re.search(r"\badj(?:usted|\.)?\b", metric.label, re.I) and not re.search(r"\badj(?:usted|\.)?\b", evidence, re.I):
            record("ADJUSTED_BASIS_MISSING")
        net = re.search(r"net (?:bank )?(cash|debt)", metric.label, re.I)
        if net and not re.search(r"net (?:bank )?" + net[1], evidence, re.I):
            record("NET_BASIS_MISSING")
        if is_balance(metric.label) and not metric.period.strip():
            record("BALANCE_DATE_REQUIRED")
        scoped = metric_evidence(metric, [r.quote for r in metric.evidence])
        if re.search(r"production|revenue|profit|runway", metric.label, re.I) and forecast_applies(metric.label + " " + metric.value, scoped):
            if not (EXPECTED.search(visible) or CONDITION.search(visible)):
                record("EXPECTED_QUALIFIER_LOST")
        if re.search(r"dividend|buyback", metric.label, re.I) and PROPOSED.search(evidence):
            if not PROPOSED.search(visible): record("PROPOSED_QUALIFIER_LOST")
        duration = (bool(re.search(r"development|duration", metric.label, re.I))
                    and any(q.unit in {"month", "year"} for q in quantities(metric.value)))
        if CONDITION.search(scoped) and not duration:
            if not (CONDITION.search(visible) or PROPOSED.search(visible)):
                record("CONDITION_LOST")
            if card.qualification is None or not (CONDITION.search(card.qualification.text) or PROPOSED.search(card.qualification.text)):
                record("QUALIFICATION_MISSING")
    # Do not suggest that year-end cash is available after a disclosed later payment.
    current_field = "card"
    full_visible = "\n".join(visible_parts)
    if any(is_balance(m.label) for m in card.metrics) or re.search(r"net (?:bank )?cash", "\n".join(visible_parts[:2]), re.I):
        # Repeated disclosures do not require repeated citations. Match each unique
        # later-payment amount to visible prose and at least one supporting quote.
        later_amounts = {q.amount for sentence in payment_sentences(selection)
                         for q in quantities(sentence) if q.unit == "GBP"}
        if later_amounts:
            shown = {q.amount for q in quantities(full_visible) if q.unit == "GBP"}
            cited = any(POST.search(a["quote"]) and PAYMENT.search(a["quote"]) for a in anchors)
            if not later_amounts.issubset(shown) or not cited or not POST.search(full_visible):
                record("SUBSEQUENT_PAYMENT_OMITTED")
    # A correction must stay visible, not just hide in citations. This matches
    # explicit opening amendment language, not an ordinary note about corrections.
    if CORRECTION.search(source[:1800]):
        if not re.search(r'correct(?:ed|ion)?|amend(?:ed|ment)|replac(?:ed|ement)', full_visible, re.I):
            record('CORRECTION_OMITTED')
    if payment_sentences(selection):
        for text in visible_parts[:2]:
            if re.search(r'(?:eliminat\w*.{0,25}net (?:bank )?debt|net (?:bank )?cash).{0,55}(?:following|after).{0,30}(?:post.year.end|payment)',text,re.I):
                record('BALANCE_TIMELINE_CONFLATED')
    # Explicit going-concern uncertainty must not disappear behind an upbeat
    # highlights card. This narrow guard is NOT a general insolvency classifier.
    uncertain = []
    for p in selection.passages:
        for paragraph in re.split(r"\n\s*\n", p.text):
            if re.search(r"material uncertaint(?:y|ies)[\s\S]{0,180}(?:cast|significant doubt)", paragraph, re.I):
                if not re.search(r"(?:no|not (?:a|any))\s+material uncertaint", paragraph, re.I):
                    uncertain.append(paragraph)
    if uncertain:
        qual = card.qualification.text if card.qualification else ""
        cited = any(a["field"] == "qualification" and
                    re.search(r"material uncertaint", a["quote"], re.I) for a in anchors)
        if not UNCERTAINTY.search(qual) or not cited:
            record("GOING_CONCERN_OMITTED")
    if findings:
        error = CardError("CARD_EVIDENCE", findings=tuple(dict.fromkeys(findings)))
        # Safe diagnostic field names/codes, never private model copy or source text.
        error.details = [dict(t) for t in dict.fromkeys(tuple(d.items()) for d in details)]
        raise error
    return {"status": "passed", "anchors": anchors,
            "scope": "Quotation, number and selected qualification checks only; not exhaustive semantic verification."}
