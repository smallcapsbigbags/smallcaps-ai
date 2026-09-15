"""Opt-in one paid submission through the deployed, no-login browser journey.

Only the fixed public TRT fixture is used. GETs/polls and rendering do not call AI.
No sign-in, no credential export, no repair, no resubmit, no fallback. Keep evidence
of failures as failures; this is a smoke test, not a long-results quality evaluation.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import requests
from playwright.sync_api import sync_playwright
from rnsrepo.public_access import build_fingerprint

ROOT=Path(__file__).resolve().parents[1]

def run(origin: str, output: Path) -> None:
    if origin!='https://smallcaps-ai-production.up.railway.app':
        raise ValueError('This opt-in check is limited to the approved demo origin')
    output.mkdir(parents=True,exist_ok=True)
    record={'live_model':True,'source':'supplied TRT fixture','max_paid_submissions':1,'passed':False}
    expected=build_fingerprint()
    # Wait only on a free readiness endpoint, and require the reviewed code fingerprint.
    for _ in range(60):
        try:
            r=requests.get(origin+'/api/v1/analyse',headers={'X-Smallcaps-Action':'prepare'},timeout=10)
            if r.status_code==200 and r.json().get('build')==expected:break
        except requests.RequestException:pass
        time.sleep(5)
    else:raise RuntimeError('Reviewed public build did not become ready; no model request sent')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1280,'height':1000})
        page=context.new_page();submitted=[];completed=[]
        def capture(resp):
            if '/api/v1/analyse/' in resp.url and '/questions' not in resp.url and resp.status==200:
                try:
                    data=resp.json()
                    if data.get('status') in ('complete','failed'):completed.append(data)
                except Exception:pass
        page.on('response',capture)
        page.on('request',lambda req: submitted.append(req.url) if req.method=='POST' and req.url.endswith('/api/v1/analyse') else None)
        try:
            page.goto(origin);assert 'RNSRepo' in page.title()
            assert page.locator('input[name="access_code"]').count()==0
            page.screenshot(path=str(output/'live-landing.png'),full_page=True)
            page.locator('#rns-text').fill((ROOT/'benchmarks/rnsrepo/trt-supplied-announcement.txt').read_text())
            started=time.monotonic();page.get_by_role('button',name='Analyse',exact=True).click()
            page.wait_for_function('document.querySelector("#result").hidden === false || document.querySelector("#form-message").dataset.error === "true"',timeout=85000)
            record['elapsed_seconds']=round(time.monotonic()-started,3)
            record['submissions']=len(submitted)
            assert len(submitted)==1
            if page.locator('#result').is_hidden():
                record['error']=page.locator('#form-message').inner_text()
                raise RuntimeError('Live generation did not return a card')
            assert completed and completed[-1]['status']=='complete'
            card=completed[-1]['result'];record['card']=card
            assert card['schema_version']=='rnsrepo-card-1' and card['integrity']['status']=='passed'
            assert card['capabilities']['questions'] is False
            assert card['telemetry']['requests']==1 and card['telemetry']['retries']==0
            assert page.locator('.materiality').count()==0
            # Observe real values and conditionality, without editing output for the screenshot.
            values=' '.join(f['value'] for f in card['facts'])
            assert '0.7' in values and '2027' in values and ('6' in values or 'six' in values.lower())
            copy=page.locator('#result').inner_text().lower()
            assert any(w in copy for w in ('subject to','conditional','following successful','depends on','contingent'))
            page.locator('#result').screenshot(path=str(output/'live-trt-desktop.png'))
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('#result').screenshot(path=str(output/'live-trt-mobile.png'))
            record.update(passed=True,build=expected)
        finally:
            if not record['passed']:page.screenshot(path=str(output/'live-failure.png'),full_page=True)
            (output/'live.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
            context.close();browser.close()
    print(json.dumps({k:v for k,v in record.items() if k!='card'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true',required=True)
    parser.add_argument('--origin',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.origin,args.output)
