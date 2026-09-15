"""Choose source IDs instead of asking a small model to recopy quotations.

The model never supplies quotation text on this wire contract. Short verbatim
source blocks are prepared locally and resolved back into the existing internal
CardDraft. The existing numerical/qualification checks remain mandatory.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from .schema import CardDraft, CardError


@dataclass(frozen=True)
class Citation:
    id: str
    passage_id: str
    quote: str


def citation_catalog(selection) -> dict[str, Citation]:
    catalog = {}
    seen = set()
    for passage in selection.passages:
        # Paragraphs retain table rows and conditions together. Oversized paragraphs
        # split at sentence/row boundaries, falling back to spaces, never rewritten.
        for paragraph in re.split(r'\n\s*\n', passage.text):
            rest = paragraph.strip()
            while rest:
                end = min(len(rest), 850)
                if len(rest) > 850:
                    cuts = [m.end() for m in re.finditer(r'[.!?]\s+|\n', rest[300:850])]
                    if cuts: end = 300 + cuts[-1]
                    else:
                        cut = rest.rfind(' ', 300, 850)
                        if cut >= 300: end = cut + 1
                quote = rest[:end].strip()
                rest = rest[end:].lstrip()
                if len(quote) < 12:
                    # Keep short table units/date headings with adjacent original
                    # context instead of dropping them. No text is manufactured.
                    at = passage.text.find(quote)
                    quote = passage.text[max(0, at - 60):min(len(passage.text), at + len(quote) + 240)].strip()
                    if len(quote) < 12:
                        continue  # Entire passage is too small for the evidence contract.
                key = (passage.heading, quote)
                if key in seen:
                    continue
                seen.add(key)
                cid = f'q{len(catalog)}'
                catalog[cid] = Citation(cid, passage.id, quote)
    if not catalog or len(catalog) > 256:
        raise CardError('CARD_SELECTION')
    return catalog


def wire_schema(catalog: dict[str, Citation]) -> dict:
    schema = CardDraft.model_json_schema()
    # Keep the same six fields and size bounds. References become source-defined IDs.
    schema['$defs']['Reference'] = {'type': 'string', 'enum': list(catalog)}
    return schema


def resolve_wire(raw: str, catalog: dict[str, Citation]) -> CardDraft:
    import json
    try:
        value = json.loads(raw)
        if not isinstance(value, dict): raise ValueError('object required')
        objects = [value.get(k) for k in ('headline','supporting_sentence','what_changed','qualification')]
        metrics = value.get('metrics', [])
        if not isinstance(metrics, list): raise ValueError('metrics must be a list')
        objects.extend(metrics)
        for obj in objects:
            if obj is None: continue
            if not isinstance(obj, dict) or not isinstance(obj.get('evidence'), list):
                raise ValueError('references required')
            refs = []
            for cid in obj['evidence']:
                if not isinstance(cid, str) or cid not in catalog:
                    raise ValueError('unknown reference')
                item = catalog[cid]
                refs.append({'passage_id': item.passage_id, 'quote': item.quote})
            obj['evidence'] = refs
        return CardDraft.model_validate(value)
    except (ValueError, TypeError, KeyError):
        raise CardError('CARD_FORMAT') from None
