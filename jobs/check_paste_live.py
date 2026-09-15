"""Opt-in, bounded live smoke test of the actual paste adapter. Never run on a schedule.

Default is preflight only: it makes no network/model request. A completed run still
requires human review for semantic accuracy and editorial quality. No secrets, raw
prompts, or pasted text are included in the default report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*, output: Path, live: bool = False, model: str = '',
        cases: tuple[str,...] = ('spr','trt'), max_output_tokens: int = 8000) -> int:
    if len(cases) > 2 or not cases or len(set(cases)) != len(cases) or not set(cases) <= {'spr','trt'}:
        raise ValueError('Select one or two distinct approved smoke-test cases: spr, trt')
    if not 2000 <= max_output_tokens <= 12000:
        raise ValueError('Output tokens must be between 2000 and 12000 per model request')
    from jobs.paste_test_cases import load_integrity_cases
    fixtures = load_integrity_cases()
    selected = [c for name in cases for c in fixtures if c['id']==name]
    if any(len(c['source']) > 12000 for c in selected):
        raise ValueError('Live smoke inputs are limited to 12000 characters per case')
    report = {'mode':'live' if live else 'preflight', 'live_model':False,
              'status':'not-run', 'model':model or None,
              'api_key_configured':bool(os.environ.get('OPENAI_API_KEY')),
              'max_model_requests':len(selected)*2, 'max_output_tokens_per_request':max_output_tokens,
              'automatic_retries':0, 'cases':[],
              'limitations':['Source excerpts, not independently authenticated full RNS documents.',
                             'Token/request bounds are not a provider-side monetary spending cap.',
                             'Passing these checks does not establish full semantic or editorial accuracy.']}
    exit_code=0
    if live and (not model.strip() or not report['api_key_configured']):
        report['status']='blocked-missing-model-or-credential'; exit_code=2
    elif not live:
        report['status']='preflight-only-no-model-request'
    else:
        # Environment changes are confined to this explicit CLI process, never Railway.
        os.environ['OPENAI_MODEL']=model
        os.environ['OPENAI_MAX_OUTPUT_TOKENS']=str(max_output_tokens)
        from analyst.paste import analyse_paste
        from product.paste import PasteRequest
        for case in selected:
            source=PasteRequest(text=case['source']); start=time.monotonic()
            entry={'case':case['id'],'source_hash':source.source_hash}
            try:
                report['live_model']=True
                result=analyse_paste(source)
                entry.update(status='bounded-checks-passed',telemetry=result.get('telemetry'),
                             integrity_status=result['integrity']['status'],
                             materiality=result['materiality'], versions=result['versions'])
                # Reader-facing copy is retained for a human quality check; not auto-approved.
                entry['card_review']={key:result[key] for key in ('headline','summary','what_changed','what_matters')}
                entry['human_review_required']=True
            except Exception as exc:
                # Provider errors can contain keys/request text: record class only.
                entry.update(status='failed',error_type=type(exc).__name__)
                exit_code=1
            entry['elapsed_seconds']=round(time.monotonic()-start,3)
            report['cases'].append(entry)
            if exit_code: break  # Stop rather than spend again after quota/quality failure.
        report['status']='smoke-checks-passed-human-review-required' if exit_code==0 else 'failed'
    report['source_files']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [ROOT/'analyst/paste.py',ROOT/'analyst/paste_evidence.py',ROOT/'analyst/paste_integrity.py',ROOT/'analyst/paste_quantities.py']}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':report['status'],'live_model':report['live_model'],'report':str(output)}))
    return exit_code


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly permit paid model requests')
    parser.add_argument('--model',default='',help='Explicit model identifier; no guessed live default')
    parser.add_argument('--case',choices=['spr','trt'],action='append')
    parser.add_argument('--max-output-tokens',type=int,default=8000)
    parser.add_argument('--output',type=Path,default=Path('/tmp/paste-live-check.json'))
    args=parser.parse_args()
    raise SystemExit(run(output=args.output,live=args.live,model=args.model,
        cases=tuple(args.case or ['spr','trt']),max_output_tokens=args.max_output_tokens))
