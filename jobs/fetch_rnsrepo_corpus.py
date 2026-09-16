"""Fetch a fixed public evaluation corpus; never ingest it into the product.

No AI, database writes, user data or secrets. Raw snapshots are short-lived CI
artifacts for source review, not a new public RNS feed or commercial data archive.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import requests

# Issuer announcements, not the distributor's generated summaries. The HTML body
# boundary is reviewed before extracting the evaluation text. No arbitrary URLs.
CORPUS = {
    'spr-results': 'springfield-properties--spr/final-results-and-publication-of-annual-report/9771558',
    'fab-correction': 'fusion-antibodies--fab/replacement-final-results-/9773630',
    'val-interims': 'valirx--val/half-year-financial-report/9771482',
    'aeo-trading': 'aeorema-communications--aeo/further-material-upgrade-to-fy2026-expectations-/9773345',
    'geo-placing': 'geo-exploration-limited--geo/capital-raise-and-retail-offer/9765472',
    'src-acquisition': 'sigmaroc--src/acquisition-of-ab-dolomitas-/9757730',
    'ng-director': 'national-grid--ng./director-pdmr-shareholding/9752717',
    'head-warning': 'headlam-group--head/trading-update-and-strategic-review/9666638',
    'hayd-commercial': 'haydale-graphene-industries--hayd/settf-commercialisation-update/9771565',
}

def fetch(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    records = []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'RNSRepo-Evaluation/1.0 (fixed-announcement acceptance test)'
        for name, path in CORPUS.items():
            url = 'https://www.investegate.co.uk/announcement/rns/' + path
            record = {'id': name, 'url': url, 'fetched_at': datetime.now(timezone.utc).isoformat()}
            try:
                response = session.get(url, timeout=(8, 20), allow_redirects=False)
                record['status_code'] = response.status_code
                response.raise_for_status()
                if response.status_code != 200 or len(response.content) > 3_000_000:
                    raise ValueError('invalid source response')
                html = response.content
                if b'<html' not in html[:2000].lower():
                    raise ValueError('not HTML')
                (output / (name + '.html')).write_bytes(html)
                record.update(bytes=len(html), sha256=hashlib.sha256(html).hexdigest(), status='fetched')
            except Exception as exc:
                record.update(status='failed', error_type=type(exc).__name__)
            records.append(record)
            time.sleep(0.2)
    (output / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(records, separators=(',', ':')))
    return int(any(r['status'] != 'fetched' for r in records))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(fetch(parser.parse_args().output))
