"""Three explicitly authorised production-browser submissions, no login or retries.

Use hash-checked public sources, never an ordinary user's paste. One short RNS,
the full Springfield release, and its one-cell-per-line copy variant. Every result
is saved honestly, including failures. This check does not certify all semantics.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time
import requests
from playwright.sync_api import sync_playwright
from jobs.rnsrepo_corpus import load_corpus
from rnsrepo.public_access import build_fingerprint

ORIGIN = 'https://smallcaps-ai-production.up.railway.app'

def run(output: Path, sources: Path | None = None) -> None:
    corpus = dict(load_corpus(sources))
    cases = [('trt-contract', corpus['trt-contract']), ('spr-results', corpus['spr-results']),
             ('spr-vertical-copy', corpus['spr-results'].replace('\t', '\n\n'))]
    output.mkdir(parents=True, exist_ok=True)
    report = {'build': build_fingerprint(), 'max_paid_submissions': 3, 'results': [],
              'live_model': True, 'exact_user_paste_tested': False}
    for _ in range(60):
        try:
            response = requests.get(ORIGIN + '/api/v1/analyse', headers={'X-Smallcaps-Action':'prepare'}, timeout=10)
            if response.status_code == 200 and response.json().get('build') == report['build']: break
        except requests.RequestException: pass
        time.sleep(5)
    else: raise RuntimeError('Reviewed build is not ready; no paid submission sent')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, source in cases:
            row = {'case': name, 'characters': len(source), 'source_hash': hashlib.sha256(source.encode()).hexdigest(), 'passed': False}
            context = browser.new_context(viewport={'width':1280,'height':1000})
            page = context.new_page(); submissions = []; terminal = []
            def capture(response):
                if '/api/v1/analyse/' in response.url and response.status == 200:
                    try:
                        data = response.json()
                        if data.get('status') in ('complete','failed'): terminal.append(data)
                    except Exception: pass
            page.on('response', capture)
            page.on('request', lambda r: submissions.append(r.url) if r.method == 'POST' and r.url.endswith('/api/v1/analyse') else None)
            try:
                page.goto(ORIGIN)
                assert 'RNSRepo' in page.title()
                assert page.locator('input[name="access_code"]').count() == 0
                page.locator('#rns-text').fill(source)
                start = time.monotonic()
                page.get_by_role('button',name='Analyse',exact=True).click()
                deadline = start + 85
                while time.monotonic() < deadline:
                    if page.locator('#result').is_visible() or page.locator('#form-message').get_attribute('data-error') == 'true': break
                    page.wait_for_timeout(200)
                row['elapsed_seconds'] = round(time.monotonic()-start,3)
                assert len(submissions) == 1
                if terminal: row['terminal_status'] = terminal[-1]['status']
                if page.locator('#result').is_hidden():
                    row['error'] = page.locator('#form-message').inner_text()
                    raise RuntimeError('No completed card')
                assert terminal and terminal[-1]['status'] == 'complete'
                card = terminal[-1]['result']; row['card'] = card
                assert card['integrity']['status'] == 'passed'
                assert card['telemetry']['requests'] == 1 and card['telemetry']['retries'] == 0
                assert card['capabilities']['questions'] is False
                text = page.locator('#result').inner_text()
                if name.startswith('spr'):
                    values = ' '.join(f['value'] for f in card['facts'])
                    assert '243.7' in values and '12.9' in values and '1.2' in values
                    assert '20.7' in text and '2026' in text
                    assert 'propos' in text.lower() and ('land sale' in text.lower())
                else:
                    assert '0.7' in text and '2027' in text
                    assert any(w in text.lower() for w in ('subject to','conditional','following successful','depends on','contingent'))
                page.locator('#result').screenshot(path=str(output/(name+'-desktop.png')))
                page.set_viewport_size({'width':390,'height':844})
                box = page.locator('#result').bounding_box()
                assert box and box['x'] >= 0 and box['x']+box['width'] <= 390.5
                page.locator('#result').screenshot(path=str(output/(name+'-mobile.png')))
                row['passed'] = True
            except Exception as exc:
                row['error_type'] = type(exc).__name__
                page.screenshot(path=str(output/(name+'-failure.png')), full_page=True)
            finally:
                row['submissions'] = len(submissions)
                report['results'].append(row)
                (output/'live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                context.close()
            # Do not repeatedly spend if a shared quota/configuration failure occurs.
            if row.get('terminal_status') is None and not row['passed']: break
        browser.close()
    report['passed'] = len(report['results']) == 3 and all(r['passed'] for r in report['results'])
    (output/'live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({**report,'results':[{k:v for k,v in r.items() if k!='card'} for r in report['results']]}))
    if not report['passed']: raise RuntimeError('One or more real browser checks did not pass')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); run(args.output, args.sources)
