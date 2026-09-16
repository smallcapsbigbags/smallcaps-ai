"""Focused checks on displayed claims, not an equity-research publication gate.

Matching numbers/quotations does not establish causal or semantic correctness. Keep
that limitation explicit; never label the original user paste independently verified.
"""
from __future__ import annotations
import re
from .schema import CardDraft, CardError
from .sections import Selection
from analyst.paste_quantities import supported_numbers, bound_preserved, quantities

EXPECTED = re.compile(r"\bexpect\w*|\bforecast\w*|\btarget\w*|\banticipat\w*", re.I)
PROPOSED = re.compile(r"\bpropos\w*|\bintend\w*|\brecommend\w*|\bplan(?:s|ned)?\b", re.I)
CONDITION = re.compile(r"subject to|depend\w*|conditional|following successful|upon successful", re.I)
POST = re.compile(r"(?:post|after|since)[- ](?:the )?(?:year|period)[- ]end|subsequent", re.I)
PAYMENT = re.compile(r"paid|payment|consideration", re.I)


def _numeric_text(text: str) -> str:
    # Equivalent disclosed bounds and UK percentage notation. These aliases do
    # not remove a floor/ceiling or create a new derived percentage.
    text = re.sub(r"\b(?:no|not) less than\b", "at least", text, flags=re.I)
    text = re.sub(r"\b(?:no|not) more than\b", "at most", text, flags=re.I)
    text = re.sub(r"\bper\s+cent\.?", "%", text, flags=re.I)
    text = re.sub(r"\((\d+(?:\.\d+)?)\)\s*(%|bps\b)", r"-\1\2", text, flags=re.I)
    text = re.sub(r"\b(?:down|decreased by|fell by)\s+(\d+(?:\.\d+)?\s*%)", r"-\1", text, flags=re.I)
    # Hyphenated numeric durations are the same quantity as their spaced source
    # form. This does not remove negative signs, change amounts or allow rounding.
    text = re.sub(r"(?<=\d)[-‐‑–](?=(?:months?|years?)\b)", " ", text, flags=re.I)
    # A fiscal-year display is an alias, not a new figure. Preserve all other digits.
    return re.sub(r"\bFY\s?(\d{2})\b", lambda m: "20" + m[1], text, flags=re.I)


def check_card(source: str, selection: Selection, card: CardDraft) -> dict:
    by_id = {p.id: p for p in selection.passages}
    anchors = []
    findings = []

    def support(refs, field: str) -> str:
        parts = []
        for ref in refs:
            passage = by_id.get(ref.passage_id)
            if passage is None:
                findings.append("UNKNOWN_PASSAGE"); continue
            rx = r"\s+".join(re.escape(w) for w in ref.quote.split())
            match = re.search(rx, passage.text)
            if match is None:
                findings.append("QUOTE_NOT_FOUND"); continue
            start, end = passage.start + match.start(), passage.start + match.end()
            quote = source[start:end]
            anchors.append({"field": field, "start": start, "end": end, "quote": quote})
            parts.append(quote)
        return "\n".join(parts)

    def check_numbers(visible: str, evidence: str) -> None:
        if not supported_numbers(_numeric_text(visible), _numeric_text(evidence)):
            findings.append("UNSUPPORTED_NUMBER")
        if not bound_preserved(_numeric_text(visible), _numeric_text(evidence)):
            findings.append("BOUND_CHANGED")

    def check_commitments(visible: str, evidence: str) -> None:
        if re.search(r"\b(?:guaranteed|debt[- ]free)\b|contracted recurring", visible, re.I):
            if not re.search(r"\b(?:not|no|isn.t)\b.{0,35}(?:guaranteed|debt[- ]free|contracted)", visible, re.I):
                if not re.search(r"guaranteed|debt[- ]free|contracted recurring", evidence, re.I):
                    findings.append("UNSUPPORTED_COMMITMENT")
        if re.search(r"net bank cash", evidence, re.I) and re.search(r"\bnet cash\b", visible, re.I):
            findings.append("BANK_BASIS_LOST")
        if re.search(r"\b(?:today|currently|now)\b.{0,30}(?:cash|debt)|(?:cash|debt).{0,30}\btoday\b", visible, re.I):
            if re.search(r"year[- ]end|period[- ]end|\bat 31\b|\bat 30\b", evidence, re.I):
                findings.append("BALANCE_DATE_CHANGED")

    visible_parts = []
    for name in ("headline", "supporting_sentence", "what_changed", "qualification"):
        statement = getattr(card, name)
        if statement is None: continue
        if not statement.text.strip(): findings.append("EMPTY_TEXT")
        evidence = support(statement.evidence, name)
        check_numbers(statement.text, evidence)
        check_commitments(statement.text, evidence)
        visible_parts.append(statement.text)
        # Forecast/proposal qualifications apply to a numerical claim, not every
        # generic description of an already awarded development programme.
        if quantities(statement.text):
            if re.search(r"revenue|production|profit|runway", statement.text, re.I) and EXPECTED.search(evidence):
                if not (EXPECTED.search(statement.text) or CONDITION.search(statement.text)):
                    findings.append("EXPECTED_QUALIFIER_LOST")
            if re.search(r"dividend|buyback", statement.text, re.I) and PROPOSED.search(evidence):
                if not PROPOSED.search(statement.text): findings.append("PROPOSED_QUALIFIER_LOST")

    seen = set()
    for i, metric in enumerate(card.metrics):
        evidence = support(metric.evidence, f"metrics.{i}")
        visible = " ".join((metric.label, metric.value, metric.period, metric.note))
        check_numbers(visible, evidence)
        check_commitments(visible, evidence)
        visible_parts.append(visible)
        if not quantities(metric.value): findings.append("METRIC_NOT_NUMERICAL")
        identity = (metric.label.lower().strip(), metric.period.lower().strip())
        if identity in seen: findings.append("DUPLICATE_METRIC")
        seen.add(identity)
        # Short quoted context must identify the metric, not merely contain its number.
        aliases = [(r"revenue|sales", r"revenue|sales"), (r"dividend", r"dividend"),
            (r"cash|debt", r"cash|debt"), (r"pbt|profit", r"pbt|profit"),
            (r"production", r"production"), (r"develop", r"develop"),
            (r"issue price|placing price", r"issue price|placing price|per share|pence|\bp\b")]
        for label_rx, evidence_rx in aliases:
            if re.search(label_rx, metric.label, re.I) and not re.search(evidence_rx, evidence, re.I):
                findings.append("METRIC_BASIS_MISSING")
        if re.search(r"\badj(?:usted|\.)?\b", metric.label, re.I) and not re.search(r"\badj(?:usted|\.)?\b", evidence, re.I):
            findings.append("ADJUSTED_BASIS_MISSING")
        net = re.search(r"net (?:bank )?(cash|debt)", metric.label, re.I)
        if net and not re.search(r"net (?:bank )?" + net[1], evidence, re.I):
            findings.append("NET_BASIS_MISSING")
        if re.search(r"cash|debt", metric.label, re.I) and not metric.period.strip():
            findings.append("BALANCE_DATE_REQUIRED")
        if re.search(r"production|revenue|profit|runway", metric.label, re.I) and EXPECTED.search(evidence):
            if not (EXPECTED.search(visible) or CONDITION.search(visible)):
                findings.append("EXPECTED_QUALIFIER_LOST")
        if re.search(r"dividend|buyback", metric.label, re.I) and PROPOSED.search(evidence):
            if not PROPOSED.search(visible): findings.append("PROPOSED_QUALIFIER_LOST")
        duration = (bool(re.search(r"development|duration", metric.label, re.I))
                    and any(q.unit in {"month", "year"} for q in quantities(metric.value)))
        if CONDITION.search(evidence) and not duration:
            if not (CONDITION.search(visible) or PROPOSED.search(visible)):
                findings.append("CONDITION_LOST")
            if card.qualification is None or not (CONDITION.search(card.qualification.text) or PROPOSED.search(card.qualification.text)):
                findings.append("QUALIFICATION_MISSING")
    # Do not suggest that year-end cash is available after a disclosed later payment.
    full_visible = "\n".join(visible_parts)
    if any(re.search(r"cash|debt", m.label, re.I) for m in card.metrics):
        # Repeated disclosures do not require repeated citations. Match each unique
        # later-payment amount to visible prose and at least one supporting quote.
        later_amounts = set()
        for p in selection.passages:
            for match in POST.finditer(p.text):
                sentence = re.split(r"(?<=[.!?])\s+", p.text[match.start():match.start()+500])[0]
                if PAYMENT.search(sentence):
                    later_amounts.update(q.amount for q in quantities(sentence) if q.unit == "GBP")
        if later_amounts:
            shown = {q.amount for q in quantities(full_visible) if q.unit == "GBP"}
            cited = any(POST.search(a["quote"]) and PAYMENT.search(a["quote"]) for a in anchors)
            if not later_amounts.issubset(shown) or not cited or not POST.search(full_visible):
                findings.append("SUBSEQUENT_PAYMENT_OMITTED")
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
        if not re.search(r"material uncertaint", qual, re.I) or not cited:
            findings.append("GOING_CONCERN_OMITTED")
    if findings:
        raise CardError("CARD_EVIDENCE", findings=tuple(dict.fromkeys(findings)))
    return {"status": "passed", "anchors": anchors,
            "scope": "Quotation, number and selected qualification checks only; not exhaustive semantic verification."}
