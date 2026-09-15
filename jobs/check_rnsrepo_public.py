"""Real anonymous HTTP/UI journey with controlled card responses, never paid AI."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from playwright.sync_api import sync_playwright, expect

from api.frontend import create_frontend_routes
from api.paste import create_paste_routes
from api.paste_jobs import PasteJobs
from rnsrepo.public_access import budget
from rnsrepo.schema import CardError

ROOT=Path(__file__).resolve().parents[1]

@contextmanager
def server():
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{
        'RNSREPO_PUBLIC_ENABLED':'1','RNSREPO_PUBLIC_ORIGIN':origin,
        'RNSREPO_SESSION_SECRET':'test-only-browser-secret-not-production'*2,
        'DATABASE_URL':f'sqlite:///{tmp}/budget.db','PRIVATE_BETA_MODE':'true',
        'APP_BETA_PASSWORD':'test-private','WEB_CONCURRENCY':'1',
        'RAILWAY_ENVIRONMENT_ID':'','RNSREPO_DAILY_ATTEMPTS':'100','RNSREPO_HOURLY_ATTEMPTS':'30'}):
        budget.cache_clear();meter=budget();meter.initialise()
        cards=json.loads((ROOT/'benchmarks/rnsrepo/editorial-cards.json').read_text())['cards']
        calls=[]
        def runner(source):
            calls.append(source.text);time.sleep(.05)
            if 'SIMULATE_PROVIDER_FAILURE' in source.text:raise CardError('CARD_TIMEOUT')
            return cards['spr' if 'Springfield' in source.text else 'trt']
        jobs=PasteJobs(runner,owner_limit=20,hourly_limit=100)
        cfg=SimpleNamespace(openai_api_key='mock',private_beta_mode=True,app_beta_password='test-private')
        app=Starlette(routes=[*create_frontend_routes(),*create_paste_routes(lambda:jobs,lambda:cfg),
                              Mount('/assets',StaticFiles(directory=ROOT/'frontend/assets'))])
        instance=uvicorn.Server(uvicorn.Config(app,log_level='error'))
        thread=threading.Thread(target=instance.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        for _ in range(100):
            if instance.started:break
            time.sleep(.02)
        try:yield origin,cards,calls
        finally:
            instance.should_exit=True;thread.join(5);jobs.close();budget.cache_clear();meter.engine.dispose();sock.close()

def run(output: Path):
    output.mkdir(parents=True,exist_ok=True);cases=[]
    with server() as (origin,cards,calls), sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1280,'height':1000})
        page=context.new_page();page.goto(origin)
        expect(page.locator('.wordmark')).to_have_text('RNSRepo')
        assert page.locator('input[name="access_code"]').count()==0
        page.screenshot(path=str(output/'landing-desktop.png'),full_page=True)
        text=(ROOT/'benchmarks/rnsrepo/trt-supplied-announcement.txt').read_text()
        page.locator('#rns-text').fill(text);page.get_by_role('button',name='Analyse',exact=True).click()
        expect(page.locator('#result')).to_be_visible(timeout=10000)
        expect(page.locator('#result-headline')).to_have_text(cards['trt']['headline'])
        expect(page.locator('#questions')).to_be_hidden()
        assert len(calls)==1
        page.screenshot(path=str(output/'anonymous-journey.png'),full_page=True)
        # Same document in same session reuses the completed result, with no model call.
        page.get_by_role('button',name='Analyse',exact=True).click()
        expect(page.locator('#result')).to_be_visible();assert len(calls)==1
        # Render controlled visual fixtures through the actual production renderer.
        for width in (320,390,768,1280):
            page.set_viewport_size({'width':width,'height':1000})
            for name,card in cards.items():
                page.evaluate('(c)=>SmallcapsCard.render(document.getElementById("result"),c)',card)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                expect(page.locator('.materiality')).to_have_count(0)
                expect(page.locator('.metric-icon')).to_have_count(len(card['facts']))
                for i,fact in enumerate(card['facts']):
                    expect(page.locator('.metric-value').nth(i)).to_have_text(fact['value'])
                    if fact['note']:expect(page.locator('.metric').nth(i)).to_contain_text(fact['note'])
                page.locator('#result').screenshot(path=str(output/f'{name}-card-{width}.png'))
                cases.append({'width':width,'card':name,'passed':True})
            page.evaluate('(c)=>SmallcapsCard.render(document.getElementById("result"),c)',{**cards['trt'],'facts':[],'what_matters':[]})
            assert page.locator('.metric').count()==0
            assert page.locator('.qualification-strip').count()==0
            long={**cards['spr'],'headline':'Long announcement wording '*18,'what_matters':['Important contextual condition '*45]}
            page.evaluate('(c)=>SmallcapsCard.render(document.getElementById("result"),c)',long)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        # Untrusted text is rendered literally, never inserted as HTML.
        page.evaluate('(c)=>SmallcapsCard.render(document.getElementById("result"),c)',{**cards['trt'],'headline':'<img src=x onerror="window.injected=true">'})
        assert page.locator('#result img').count()==0 and page.evaluate('window.injected !== true')
        # Mobile fresh arrival and recoverable errors (do not spend a third-party call).
        page.goto(origin);page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(output/'landing-mobile.png'),full_page=True)
        bad=text+'\nSIMULATE_PROVIDER_FAILURE'
        page.locator('#rns-text').fill(bad);page.get_by_role('button',name='Analyse',exact=True).click()
        expect(page.locator('#form-message')).to_contain_text('took too long',timeout=10000)
        assert page.locator('#rns-text').input_value()==bad
        assert page.locator('#analyse-button').is_enabled()
        page.screenshot(path=str(output/'error-mobile.png'),full_page=True)
        page.locator('#rns-text').fill('x'*120001)
        expect(page.locator('#analyse-button')).to_be_disabled()
        page.emulate_media(reduced_motion='reduce')
        assert page.evaluate('getComputedStyle(document.querySelector(".composer")).transitionDuration')=='0s'
        context.close();browser.close()
    report={'live_model':False,'real_anonymous_http':True,'cases':cases,'extra_checks':['no login','duplicate free','safe DOM','empty metrics','long content','error preserves source','oversized input','reduced motion']}
    (output/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);run(parser.parse_args().output)
