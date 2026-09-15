"""Served-browser card acceptance with schema-validated fixture notes, never live AI."""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

from analyst.models import AnalystNote
from product.paste import PasteRequest, project_paste_result

ROOT = Path(__file__).resolve().parents[1]


def layout(page):
    issues = page.evaluate("""() => {
      const width = document.documentElement.clientWidth;
      const issues = [];
      if (document.documentElement.scrollWidth > width + 1) issues.push('page overflow');
      for (const el of document.querySelectorAll('.metric, .metric-value, .metric-note')) {
        if (el.scrollWidth > el.clientWidth + 1) issues.push('metric overflow: ' + el.className);
      }
      const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
      if (new Set(ids).size !== ids.length) issues.push('duplicate IDs');
      return issues;
    }""")
    assert not issues, issues


def run(base: str, out: Path, executable: str | None = None):
    if urlparse(base).hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Use a local server; all model results here are test fixtures.')
    cases = json.loads((ROOT / 'tests/fixtures/paste_card_cases.json').read_text(encoding='utf-8'))
    out.mkdir(parents=True, exist_ok=True)
    report = {'live_model': False, 'method': 'Actual served assets; API intercepted with schema-validated fixture projections.', 'checks': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
        for device, width, height in [('desktop',1440,1000),('tablet',768,1024),('mobile',390,844),('narrow',320,740)]:
            context = browser.new_context(viewport={'width':width,'height':height}, reduced_motion='reduce')
            page = context.new_page()
            errors, requests = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            state = {'posts': 0, 'card': None}
            def fixture(route):
                if route.request.method == 'POST':
                    state['posts'] += 1
                    route.fulfill(json={'analysis_id':'card-fixture','status':'complete','result':state['card']})
                else:
                    route.fulfill(json={'ready':True})
            page.route(re.compile(r'/api/v1/analyse(?:/[^?]*)?(?:\?.*)?$'), fixture)
            page.goto(base, wait_until='networkidle')
            page.evaluate('document.fonts.ready')
            expect(page.get_by_role('heading',name='See what matters.',exact=True)).to_be_visible()
            assert not any('/api/' in url for url in requests)
            assert page.locator('nav').count() == 0
            page.screenshot(path=out / f'landing-{device}.png',full_page=True)
            for case in cases:
                source = PasteRequest(text=case['source'])
                note = AnalystNote(source_id=source.source_id, **case['note'])
                state['card'] = project_paste_result(source,note)
                card = state['card']
                assert card['metric_indexes'] == case['expected_metric_indexes']
                page.locator('#rns-text').fill(source.text)
                page.locator('#analyse-button').click()
                expect(page.locator('#result')).to_be_visible()
                expect(page.locator('#analyse-button')).to_be_enabled()
                expect(page.locator('#result-headline')).to_have_text(note.headline)
                expect(page.locator('#result')).to_contain_text(note.analyst_view)
                expect(page.locator('#result')).to_have_attribute('data-direction',card['direction'])
                assert page.locator('.metric-icon').count() == len(card['metric_indexes'])
                assert page.locator('.ticker').count() == (1 if card['identity']['ticker'] else 0)
                for i in card['metric_indexes']:
                    fact = card['facts'][i]
                    tile = page.locator(f'.metric[data-fact-index="{i}"]')
                    expect(tile.locator('.metric-value')).to_have_text(fact['value'])
                    expect(tile.locator('.metric-label')).to_have_text(fact['label'])
                    if fact['note']: expect(tile).to_contain_text(fact['note'])
                    if fact['period']: expect(tile).to_contain_text(fact['period'])
                    if fact['as_of_date']: expect(tile).to_contain_text(fact['as_of_date'])
                for fact in card['facts']:
                    if fact['basis'] == 'source-warning':
                        expect(page.locator('.what-matters')).to_contain_text(fact['value'])
                if case['id'] == 'sparse':
                    assert page.locator('.metrics').count() == 0
                    assert page.locator('.source-date').count() == 0
                expect(page.locator('.source-note')).to_contain_text('Not independently verified')
                layout(page)
                page.locator('#result').screenshot(path=out / f'{case["id"]}-card-{device}.png')
                if device in {'desktop','mobile'} and case['id'] == 'spr':
                    page.screenshot(path=out / f'result-{device}.png',full_page=True)
                before = len(requests)
                impact = page.locator('.materiality summary')
                assert impact.bounding_box()['height'] >= 44
                impact.focus()
                impact.press('Enter')
                expect(page.locator('.materiality p')).to_be_visible()
                expect(page.locator('.materiality p')).to_have_text(note.impact_rationale)
                impact.press('Enter')
                remaining = len(card['facts']) - len(card['metric_indexes'])
                if remaining:
                    page.locator('.more-facts summary').click()
                    assert page.locator('.fact-row').count() == remaining
                    for i, fact in enumerate(card['facts']):
                        if i not in card['metric_indexes']:
                            expect(page.locator(f'.fact-row[data-fact-index="{i}"]')).to_contain_text(fact['value'])
                    layout(page)
                    page.locator('.more-facts summary').click()
                assert len(requests) == before, 'Disclosure toggles must not request another analysis.'
                assert len(page.locator('[data-fact-index]').all()) == len(card['facts'])
                assert not errors, errors
                report['checks'].append({'case':case['id'],'viewport':device,'width':width,'passed':True})
            # Long text, calculation provenance, hostile output and invalid dates.
            stress = copy.deepcopy(state['card'])
            stress['identity']['publication_date'] = '2026-02-31'
            stress['summary'] = '<img src=x onerror="window.unsafeExecuted=true">'
            stress['facts'] = [{'label':'Calculated margin','value':'11.1%', 'metric':'margin', 'basis':'calculated',
                               'note':'Calculated from £4.7m / £42.4m. ' + 'Full context. ' * 50 + 'Still conditional on successful deployment.'}]
            stress['metric_indexes'] = [0]
            stress['what_matters'] = ['Important qualification. ' * 60 + 'This final condition must not disappear.']
            state['card'] = stress
            page.locator('#rns-text').fill(cases[-1]['source'] + '\nTest variant.')
            page.locator('#analyse-button').click()
            expect(page.locator('#result')).to_be_visible()
            assert page.locator('#result img').count() == 0
            assert page.evaluate('window.unsafeExecuted === undefined')
            assert page.locator('.source-date').count() == 0
            expect(page.locator('.fact-basis')).to_have_text('Calculated')
            expect(page.locator('.metric-note')).to_contain_text('Still conditional on successful deployment.')
            expect(page.locator('.what-matters')).to_contain_text('This final condition must not disappear.')
            layout(page)
            assert not errors, errors
            assert state['posts'] == len(cases) + 1
            context.close()
        browser.close()
    report['passed'] = True
    (out / 'card-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8501')
    parser.add_argument('--output', type=Path, default=Path('/tmp/paste-card-browser'))
    parser.add_argument('--chromium-executable', default=None)
    args = parser.parse_args()
    run(args.base,args.output,args.chromium_executable)
