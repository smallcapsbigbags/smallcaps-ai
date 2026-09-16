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
        # Pack adjacent original paragraphs/rows into modest contiguous excerpts.
        # Do not duplicate 240 characters for EACH short table cell or emit a huge
        # enum of one-line fragments. Every quote remains an exact source slice.
        at = 0
        while at < len(passage.text):
            while at < len(passage.text) and passage.text[at].isspace(): at += 1
            if at >= len(passage.text): break
            remaining = len(passage.text) - at
            end = at + min(850, remaining)
            if remaining > 850:
                cuts = [at + m.end() for m in re.finditer(r"\n\s*\n|[.!?]\s+|\n", passage.text[at:at+850])
                        if m.end() >= 200]
                preferred = [c for c in cuts if c-at <= 600]
                if preferred: end = preferred[-1]
                elif cuts: end = cuts[0]
                else:
                    cut = passage.text.rfind(' ', at+300, at+850)
                    if cut >= at+300: end = cut+1
            quote = passage.text[at:end].strip()
            if len(quote) < 12:
                # Tiny final heading/units retain adjacent original context once.
                quote = passage.text[max(0, at-80):end].strip()
            at = end
            if len(quote) < 12: continue
            key = (passage.id, quote)
            if key in seen: continue
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
