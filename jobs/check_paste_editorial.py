"""2B acceptance on served assets, with schema-validated MANUAL notes; never live AI."""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

from analyst.models import AnalystNote
from analyst.paste_editorial import PASTE_EDITORIAL_VERSION
from product.paste import PasteRequest, project_paste_result

ROOT = Path(__file__).resolve().parents[1]


def layout(page):
    assert page.evaluate("""() => {
      const width = document.documentElement.clientWidth;
      return document.documentElement.scrollWidth <= width + 1 &&
        [...document.querySelectorAll('.metric, .metric-value, .metric-note, .qualification-copy')]
          .every(el => el.scrollWidth <= el.clientWidth + 1);
    }"""), "Horizontal overflow"


def run(base: str, out: Path, executable: str | None = None):
    if urlparse(base).hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Use a local server. Never target a live paid endpoint.')
    cases = json.loads((ROOT / 'tests/fixtures/paste_editorial_cases.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    report = {'live_model': False, 'editorial_version': PASTE_EDITORIAL_VERSION,
              'method': 'Actual served assets; API intercepted with schema-validated manually edited notes.', 'checks': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
        for device, width, height in [('desktop',1440,1000),('tablet',768,1024),('mobile',390,844),('narrow',320,740)]:
            context = browser.new_context(viewport={'width':width,'height':height}, reduced_motion='reduce')
            page = context.new_page()
            errors, requests = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            state = {'card': None, 'posts': 0}
            def fixture(route):
                if route.request.method == 'POST':
                    state['posts'] += 1
                    route.fulfill(json={'analysis_id':'editorial-fixture','status':'complete','result':state['card']})
                else:
                    route.fulfill(json={'ready':True})
            page.route(re.compile(r'/api/v1/analyse(?:/[^?]*)?(?:\?.*)?$'), fixture)
            page.goto(base, wait_until='networkidle')
            expect(page.get_by_role('heading',name='See what matters.',exact=True)).to_be_visible()
            assert not any('/api/' in url for url in requests)
            assert page.locator('nav').count() == 0
            page.screenshot(path=out / f'landing-{device}.png',full_page=True)
            for case in cases:
                source = PasteRequest(text=case['source'])
                note = AnalystNote(source_id=source.source_id, **case['note'])
                card = project_paste_result(source,note)
                card['versions'] = {'editorial': PASTE_EDITORIAL_VERSION}  # mirrors adapter metadata
                state['card'] = card
                page.locator('#rns-text').fill(source.text)
                page.locator('#analyse-button').click()
                expect(page.locator('#result')).to_be_visible()
                expect(page.locator('#result-headline')).to_have_text(note.headline)
                expect(page.locator('#result')).to_have_attribute('data-layout','paste-card-2b')
                assert page.get_by_role('heading',name='What matters',exact=True).count() == 0
                assert page.locator('.qualification-strip h3').count() == 0
                for caveat in note.challenges_case:
                    expect(page.locator('.qualification-copy')).to_contain_text(caveat)
                    expect(page.locator('.qualification-copy')).to_be_visible()
                for i in card['metric_indexes']:
                    fact = card['facts'][i]
                    tile = page.locator(f'.metric[data-fact-index="{i}"]')
                    expect(tile.locator('.metric-value')).to_have_text(fact['value'])
                    expect(tile.locator('.metric-label')).to_have_text(fact['label'])
                    for field in ('note','period','as_of_date','previous_value'):
                        if fact[field]:
                            expect(tile).to_contain_text(fact[field])
                    expect(tile).to_be_visible()
                    if width == 1440:
                        assert tile.locator('svg').bounding_box()['width'] >= 40
                if case['id'] == 'trt':
                    assert page.locator('#result > .what-changed').count() == 0
                    expect(page.locator('.detail-changed')).to_be_hidden()
                    assert page.locator('.ticker').count() == 0
                else:
                    expect(page.locator('#result > .what-changed')).to_be_visible()
                    expect(page.locator('.qualification-strip')).to_contain_text('£20.7m')
                expect(page.locator('.source-note')).to_contain_text('Not independently verified')
                layout(page)
                page.locator('#result').screenshot(path=out / f'{case["id"]}-card-{device}.png')
                before = len(requests)
                detail = page.locator('.more-facts > summary')
                detail.focus()
                detail.press('Enter')
                expect(page.locator('.more-facts')).to_have_attribute('open','')
                if case['id'] == 'trt':
                    expect(page.locator('.detail-changed')).to_be_visible()
                    expect(page.locator('.detail-changed')).to_contain_text(note.what_changed.today)
                expect(page.locator('.detail-analysis')).to_be_visible()
                expect(page.locator('.detail-analysis')).to_contain_text(note.analyst_view)
                layout(page)
                detail.press('Enter')
                impact = page.locator('.materiality summary')
                assert impact.bounding_box()['height'] >= 44
                impact.click()
                expect(page.locator('.materiality p')).to_be_visible()
                impact.click()
                assert len(requests) == before, 'Expanding detail must not request another model call'
                assert not errors, errors
                report['checks'].append({'case':case['id'],'width':width,'passed':True})
            # Stress the renderer directly without submitting another paid analysis.
            stress = copy.deepcopy(state['card'])
            stress['what_matters'] = ['Long qualification. ' * 60 + 'The final condition stays visible.']
            stress['facts'].append({'label':'Source issue','value':'Conflicting source amounts','basis':'source-warning','note':'Do not rely on these figures.'})
            stress['summary'] = '<img src=x onerror="window.unsafeExecuted=true">'
            stress['identity']['publication_date'] = '2026-02-31'
            page.evaluate('(card) => SmallcapsCard.render(document.getElementById("result"), card)', stress)
            expect(page.locator('.qualification-copy')).to_contain_text('The final condition stays visible.')
            expect(page.locator('.qualification-copy')).to_contain_text('Conflicting source amounts')
            assert page.locator('#result img').count() == 0
            assert page.evaluate('window.unsafeExecuted === undefined')
            assert page.locator('.source-date').count() == 0
            layout(page)
            # A clean new-style note is not forced into an amber warning.
            clean = copy.deepcopy(state['card'])
            clean['what_matters'] = []
            clean['analyst_view'] = 'The announced order adds to the disclosed backlog.'
            page.evaluate('(card) => SmallcapsCard.render(document.getElementById("result"), card)', clean)
            assert page.locator('.qualification-strip').count() == 0
            expect(page.locator('.result-commentary')).to_have_text(clean['analyst_view'])
            # Legacy responses keep their full interpretation visible on upgrade.
            clean.pop('versions')
            clean['analyst_view'] = 'Legacy condition must remain visible.'
            page.evaluate('(card) => SmallcapsCard.render(document.getElementById("result"), card)', clean)
            expect(page.locator('.qualification-copy')).to_contain_text(clean['analyst_view'])
            expect(page.locator('.qualification-copy')).to_be_visible()
            assert not errors, errors
            assert state['posts'] == len(cases)
            context.close()
        browser.close()
    report['passed'] = True
    (out/'editorial-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:8501')
    parser.add_argument('--output',type=Path,default=Path('/tmp/paste-editorial-browser'))
    parser.add_argument('--chromium-executable',default=None)
    args = parser.parse_args()
    run(args.base,args.output,args.chromium_executable)
