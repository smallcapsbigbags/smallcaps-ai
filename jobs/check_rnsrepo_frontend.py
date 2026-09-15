"""Actual card renderer checks with controlled data. No model or network requests."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import runpy
from playwright.sync_api import sync_playwright
from product.paste import PasteRequest
from rnsrepo.extractor import project_card
from rnsrepo.validation import check_card


def run(output: Path) -> None:
    root=Path(__file__).resolve().parents[1]
    fixture=runpy.run_path(str(root/'tests/rnsrepo/test_card.py'))
    text=fixture['TRT']; selection, draft=fixture['draft']()
    card=project_card(PasteRequest(text=text),draft,selection,check_card(text,selection,draft))
    css=(root/'frontend/assets/analysis-card.css').read_text()
    script=(root/'frontend/assets/analysis-card.js').read_text()
    results=[];output.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,
                                  args=['--no-sandbox'])
        for width in (320,390,768,1280):
            page=browser.new_page(viewport={'width':width,'height':1100})
            page.set_content('<style>:root {--surface:#fff;--green:#39865f;--amber:#a36d14;--line:#e8ece7;--muted:#68717d;} body{margin:16px;background:#f6f7f4;font-family:Arial,sans-serif;} .result{box-sizing:border-box;max-width:1080px;margin:20px auto;}</style><style>'+css+'</style><article class="result" id="card"></article>')
            page.add_script_tag(content=script)
            page.evaluate('(c)=>SmallcapsCard.render(document.getElementById("card"),c)',card)
            assert page.locator('.metric').count()==3
            assert page.locator('.materiality').count()==0
            assert page.locator('.more-facts').count()==0
            assert page.locator('.qualification-strip').count()==1
            assert page.locator('#card').get_attribute('data-direction')=='brand'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(output/f'compact-card-{width}.png'),full_page=True)
            # Source/model text is always text, never executable HTML.
            malicious={**card,'headline':'<img src=x onerror="window.injected=true">'}
            page.evaluate('(c)=>SmallcapsCard.render(document.getElementById("card"),c)',malicious)
            assert page.locator('#card img').count()==0
            assert page.evaluate('window.injected !== true')
            results.append({'width':width,'passed':True});page.close()
        browser.close()
    (output/'checks.json').write_text(json.dumps({'live_model':False,'cases':results},indent=2))
    print(json.dumps({'passed':len(results),'live_model':False}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('/tmp/rnsrepo-renderer'))
    run(p.parse_args().output)
