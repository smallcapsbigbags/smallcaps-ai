"""Opt-in one-request smoke check. Preflight is free; never approves a launch.

Only the known TRT fixture may emit card copy in logs. Operator-supplied source
text and model copy are not logged. No retries, repair, questions or escalation.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from product.paste import PasteRequest
from rnsrepo.extractor import CardExtractor, DEFAULT_MODEL, request_kwargs
from rnsrepo.schema import CardError


def run(*, live: bool = False, source_file: Path | None = None, output: Path | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    source = PasteRequest(text=(source_file or root/'benchmarks/rnsrepo/trt-supplied-announcement.txt').read_text(encoding='utf-8'))
    model = os.getenv('RNSREPO_CARD_MODEL', DEFAULT_MODEL)
    kwargs, selection = request_kwargs(source, model)
    record = {"check": "rnsrepo-card", "model": model, "live": live, "max_requests": 1,
        "source_hash": source.source_hash, "source_kind": "operator-supplied" if source_file else "supplied-TRT-announcement",
        "selection": selection.record(), "output_token_limit": kwargs['max_output_tokens'],
        "status": "preflight-only", "launch_approved": False}
    code = 0
    if live:
        try:
            result = CardExtractor(os.getenv('OPENAI_API_KEY',''), model).extract(source)
            record.update(status='passed-needs-human-review', telemetry=result['telemetry'])
            if source_file is None:
                record['card'] = {k: result[k] for k in ('headline','summary','facts','what_changed','what_matters')}
        except CardError as exc:
            record.update(status='failed', error_code=exc.code, findings=list(exc.findings),
                          telemetry=getattr(exc,'telemetry',{})); code = 1
        except Exception as exc:
            record.update(status='failed', error_type=type(exc).__name__); code=1
    encoded = json.dumps(record,ensure_ascii=False,separators=(',',':'))
    if output:
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(encoded+'\n',encoding='utf-8')
    print(encoded,flush=True)
    return code


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--live',action='store_true')
    p.add_argument('--source',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    raise SystemExit(run(live=args.live,source_file=args.source,output=args.output))
