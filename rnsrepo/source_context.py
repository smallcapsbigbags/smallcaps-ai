"""Small source-defined obligations for a compact card; no additional model call.

These are explicit disclosures, not a general semantic risk detector. Every ID
is resolved from the selected original text, and no amount is invented.
"""
from __future__ import annotations
import re
from .financial_context import reporting_context
from analyst.paste_quantities import quantities

POST = re.compile(r'(?:post|after|since)[-‐‑ ](?:the )?(?:year|period)[-‐‑ ]end|subsequent', re.I)
PAYMENT = re.compile(r'paid|payments?|deferred consideration', re.I)
CORRECTION = re.compile(r'following amendment|(?:amended|replacement|corrected) announcement|figure should be|correction to', re.I)


def payment_sentences(selection):
    """Keep the same sentence on both sides of timing words, including £20.7m."""
    result = []
    for p in selection.passages:
        for match in POST.finditer(p.text):
            left = list(re.finditer(r'[.!?]\s+|\n\s*\n', p.text[:match.start()]))
            start = left[-1].end() if left else 0
            sentence = re.split(r'(?<=[.!?])\s+|\n\s*\n', p.text[start:match.end()+500])[0].strip()
            if not PAYMENT.search(sentence): continue
            values = [q for q in quantities(sentence) if q.unit == 'GBP']
            if values and sentence not in result: result.append(sentence)
    return result


def required_context(source, selection, catalog):
    output = []
    for sentence in payment_sentences(selection):
        refs = [c.id for c in catalog.values() if sentence in c.quote]
        # If a long sentence straddles two excerpts, both exact parts are supplied.
        if not refs:
            refs = [c.id for c in catalog.values() if c.quote in sentence and POST.search(c.quote)]
        amounts = re.findall(r'£\s*\d[\d,]*(?:\.\d+)?\s*(?:m(?:illion)?|k|bn)?', sentence, re.I)
        if refs:
            output.append({'rule':'If discussing cash or net debt, state these later payments AND their timing in qualification. Do not imply they caused the earlier year-end balance.',
                           'amounts':amounts,'evidence':refs[:2]})
    for c in catalog.values():
        if CORRECTION.search(c.quote) and source.find(c.quote) < 1800:
            output.append({'rule':'Mention that this is a correction/replacement and use the corrected figures, not the superseded ones.', 'evidence':[c.id]})
            break
    for c in catalog.values():
        if re.search(r'material uncertaint(?:y|ies)', c.quote, re.I) and re.search(r'going concern|significant doubt', c.quote, re.I):
            if not re.search(r'(?:no|not (?:a|any))\s+material uncertaint', c.quote, re.I):
                output.append({'rule':'State the disclosed material uncertainty over going concern in qualification.', 'evidence':[c.id]})
                break
    return output[:6]


def period_context(source, catalog):
    span = reporting_context(source)
    if span is None: return None
    quote = source[slice(*span)]
    refs = [c.id for c in catalog.values() if quote in c.quote]
    return {'text':quote, 'evidence':refs[:1]} if refs else None
