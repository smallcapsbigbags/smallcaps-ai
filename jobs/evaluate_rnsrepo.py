"""Explicit, bounded live evaluation; NEVER a public API or automatic model retry.

Only committed, hash-checked public source fixtures can emit model copy. The
production evidence gate still runs. This collects results; it does NOT certify
semantic accuracy or approve a launch. Runtime model/budgets are not changed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import time
from unittest.mock import patch
from product.paste import PasteRequest
from rnsrepo.extractor import CardExtractor, check_card, request_kwargs, encoded_request_bytes
from rnsrepo.public_access import build_fingerprint
from rnsrepo.schema import CardError
from rnsrepo.citations import citation_catalog
from jobs.rnsrepo_corpus import load_corpus

# Standard prices per million tokens, verified against official model pages on
# 16 September 2026. Observed usage is priced including failed attempts. This is
# an estimate, not the provider invoice or a permanent pricing guarantee.
PRICES = {'gpt-5-mini': (.25, .025, 2), 'gpt-5-nano': (.05, .005, .4),
          'gpt-4.1-nano': (.1, .025, .4), 'gpt-5.4-nano': (.2, .02, 1.25)}


def cost(usage):
    values = [usage.get(k) for k in ('input_tokens', 'output_tokens')]
    if any(v is None for v in values): return None
    inp, cached, out = PRICES[usage['model']]
    cache = usage.get('cached_input_tokens') or 0
    return round(((values[0]-cache)*inp + cache*cached + values[1]*out)/1_000_000, 8)


def card_copy(card):
    return {'type': card.announcement_type, 'headline': card.headline.text,
            'summary': card.supporting_sentence.text,
            'metrics': [{k: getattr(m, k) for k in ('label','value','period','note')} for m in card.metrics],
            'what_changed': card.what_changed.text if card.what_changed else '',
            'qualification': card.qualification.text if card.qualification else ''}


def evaluate(*, live=False, models=('gpt-5-mini', 'gpt-5-nano'), directory=None, output=None, cases=None):
    if not 1 <= len(models) <= 2 or len(set(models)) != len(models) or any(m not in PRICES for m in models):
        raise ValueError('At most two approved small models')
    corpus = load_corpus(directory)  # Verify ALL sources before any paid work.
    if cases:
        wanted = set(cases)
        if wanted - {n for n, _ in corpus}: raise ValueError('Unknown case')
        corpus = [(n, t) for n, t in corpus if n in wanted]
    if not corpus or len(corpus)*len(models) > 20: raise ValueError('20-call hard test limit')
    report = {'build': build_fingerprint(), 'live': live, 'launch_approved': False,
              'max_requests': len(corpus)*len(models) if live else 0, 'results': []}
    started = time.monotonic()
    for model in models:
        for name, text in corpus:
            if time.monotonic()-started > 780: raise TimeoutError('Evaluation wall-time bound')
            row = {'case': name, 'model': model, 'characters': len(text), 'status': 'preflight'}
            captured = []
            def checked(source, selection, draft):
                catalog = citation_catalog(selection)
                refs = {}
                for key, obj in [(k,getattr(draft,k)) for k in ('headline','supporting_sentence','what_changed','qualification')] + [(f'metrics.{i}',m) for i,m in enumerate(draft.metrics)]:
                    if obj is not None:
                        refs[key]=[next(c.id for c in catalog.values() if c.passage_id==r.passage_id and c.quote==r.quote) for r in obj.evidence]
                captured.append((card_copy(draft), refs))
                return check_card(source, selection, draft)  # NEVER bypass the gate.
            try:
                source = PasteRequest(text=text)
                kwargs, selection = request_kwargs(source, model)
                row.update(request_bytes=encoded_request_bytes(kwargs), selection=selection.record())
                if live:
                    with patch('rnsrepo.extractor.check_card', side_effect=checked):
                        result = CardExtractor(os.environ.get('OPENAI_API_KEY',''), model).extract(source)
                    row.update(status='passed', telemetry=result['telemetry'], identity=result['identity'])
            except CardError as exc:
                row.update(status=exc.code, findings=list(exc.findings), telemetry=getattr(exc,'telemetry',{}))
            except Exception as exc:
                row.update(status='harness_error', error_type=type(exc).__name__)
            if captured: row['candidate'], row['references'] = captured[-1]
            if row.get('telemetry'): row['estimated_usd'] = cost(row['telemetry'])
            report['results'].append(row)
            # A single modest record per attempt; public fixture only, no provider
            # error body, request/response credentials, private source or secret.
            print('rnsrepo_eval ' + json.dumps(row,ensure_ascii=False,separators=(',',':')),flush=True)
            if output: output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    report['elapsed_seconds'] = round(time.monotonic()-started,3)
    report['observed_estimated_usd'] = round(sum(r.get('estimated_usd') or 0 for r in report['results']),8)
    report['unpriced_attempts'] = sum(bool(r.get('telemetry',{}).get('requests')) and r.get('estimated_usd') is None for r in report['results'])
    if output: output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('rnsrepo_eval_summary ' + json.dumps({k:v for k,v in report.items() if k!='results'},separators=(',',':')),flush=True)
    return report

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--models',default='gpt-5-mini,gpt-5-nano')
    parser.add_argument('--cases',default='')
    parser.add_argument('--sources',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    evaluate(live=args.live,models=tuple(args.models.split(',')),directory=args.sources,
             output=args.output,cases=tuple(filter(None,args.cases.split(','))))
