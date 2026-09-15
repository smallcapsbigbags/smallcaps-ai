"""No paid requests. Anonymous access, ownership and durable admission controls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
import os
import runpy
import time

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.exc import OperationalError
from starlette.applications import Starlette
from starlette.testclient import TestClient

from api.paste import create_paste_routes
from api.paste_jobs import PasteJobs
from api.paste_questions import create_question_routes
from api.frontend import create_frontend_routes
from product.paste import PasteRequest
from rnsrepo.public_access import (DemoBudget, PublicConfig, PublicAccessError, counters,
                                  COOKIE, COOKIE_PATH, budget)
from rnsrepo.extractor import project_card
from rnsrepo.validation import check_card

FIXTURE = runpy.run_path(str(Path(__file__).with_name('test_card.py')))
TRT = FIXTURE['TRT']

@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv('RNSREPO_PUBLIC_ENABLED','1')
    monkeypatch.setenv('RNSREPO_PUBLIC_ORIGIN','https://testserver')
    monkeypatch.setenv('RNSREPO_SESSION_SECRET','local-test-secret-not-a-credential'*2)
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path}/budget.db')
    monkeypatch.setenv('PRIVATE_BETA_MODE','true')
    monkeypatch.setenv('APP_BETA_PASSWORD','test-private-beta')
    monkeypatch.setenv('WEB_CONCURRENCY','1')
    monkeypatch.delenv('RAILWAY_ENVIRONMENT_ID',raising=False)
    budget.cache_clear()
    b=budget(); b.initialise()
    yield b
    budget.cache_clear(); b.engine.dispose()

@pytest.fixture
def app(env):
    calls=[]
    s,c=FIXTURE['draft']()
    result=project_card(PasteRequest(text=TRT),c,s,check_card(TRT,s,c))
    def run(source): calls.append(source.text); return result
    jobs=PasteJobs(run,owner_limit=20,hourly_limit=100)
    cfg=SimpleNamespace(openai_api_key='mock-no-paid-requests',private_beta_mode=True,app_beta_password='test-private-beta')
    app=Starlette(routes=[*create_frontend_routes(), *create_paste_routes(lambda:jobs,lambda:cfg),
                         *create_question_routes(settings_provider=lambda:cfg)])
    yield app,jobs,calls
    jobs.close()

def client(app):
    # Concrete network peer; caller-supplied X-Forwarded-For remains irrelevant.
    return TestClient(app,base_url='https://testserver',client=('192.0.2.1',50000))

def prepare(c):
    r=c.get('/api/v1/analyse',headers={'X-Smallcaps-Action':'prepare'})
    assert r.status_code==200,r.text
    return {'Origin':'https://testserver','X-Smallcaps-Action':'analyse','X-RNSRepo-Token':r.json()['csrf_token']}

def send(c,h,text=TRT):
    return c.post('/api/v1/analyse',headers=h,json={'text':text})

def total(b):
    with b.engine.connect() as cx:
        return cx.execute(select(func.sum(counters.c.attempts)).where(counters.c.bucket.like('global:day:%'))).scalar() or 0

def test_anonymous_journey_no_login_but_old_routes_still_private(app,env):
    a,jobs,calls=app
    with client(a) as c:
        home=c.get('/')
        assert 'RNS<span>Repo' in home.text and 'access_code' not in home.text
        assert 'access_code' in c.get('/rns').text
        h=prepare(c)
        cookie=str(c.cookies)
        assert COOKIE in cookie
        r=send(c,h); assert r.status_code in (200,202)
        job=r.json()['analysis_id']
        for _ in range(30):
            body=c.get('/api/v1/analyse/'+job).json()
            if body['status']=='complete': break
            time.sleep(.01)
        assert body['status']=='complete' and body['result']['capabilities']['scores'] is False
        assert len(calls)==1 and total(env)==1
        assert c.get('/api/v1/analyse/'+job+'/questions').status_code==401
        assert send(c,h).json()['analysis_id']==job
        assert len(calls)==1 and total(env)==1
        with client(a) as other:
            prepare(other)
            assert other.get('/api/v1/analyse/'+job).status_code==404

def test_cookie_is_http_only_same_site_secure_and_no_account(app):
    with client(app[0]) as c:
        r=c.get('/api/v1/analyse',headers={'X-Smallcaps-Action':'prepare'})
        cookie=r.headers['set-cookie']
        assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=strict' in cookie
        assert 'Domain=' not in cookie and COOKIE_PATH in cookie
        assert r.headers['cache-control']=='no-store'

@pytest.mark.parametrize('change', ['origin','missing-origin','csrf','missing-cookie','evil-host','fetch-site','content-type','action'])
def test_rejects_bad_admission_before_spend(app,env,change):
    with client(app[0]) as c:
        h=prepare(c)
        if change=='origin':h['Origin']='https://evil.example'
        if change=='missing-origin':h.pop('Origin')
        if change=='csrf':h['X-RNSRepo-Token']='incorrect'
        if change=='missing-cookie':c.cookies.clear()
        if change=='evil-host':h['Host']='evil.example'
        if change=='fetch-site':h['Sec-Fetch-Site']='cross-site'
        if change=='content-type':h['Content-Type']='text/plain'
        if change=='action':h['X-Smallcaps-Action']='ask'
        assert send(c,h).status_code in (403,415)
        assert not app[2] and total(env)==0

@pytest.mark.parametrize('text', ['short', '<html>'+('x'*500)+'</html>', TRT*2, 'x'*120001])
def test_input_validation_free_before_reservation(app,env,text):
    with client(app[0]) as c:
        assert send(c,prepare(c),text).status_code in (413,422)
        assert total(env)==0 and not app[2]

def test_missing_schema_fails_closed(app,env):
    counters.drop(env.engine)
    with client(app[0]) as c:
        r=send(c,prepare(c));assert r.status_code==503
        assert r.json()['error']['code']=='DEMO_BUDGET_UNAVAILABLE' and not app[2]

def test_kill_switch_and_bad_configuration_fail_closed(app,env,monkeypatch):
    with client(app[0]) as c:
        h=prepare(c)
        monkeypatch.setenv('PASTE_ANALYSIS_ENABLED','false')
        assert send(c,h).status_code==503
        monkeypatch.setenv('PASTE_ANALYSIS_ENABLED','true')
        monkeypatch.setenv('RNSREPO_SESSION_SECRET','weak')
        assert send(c,h).status_code==503
        assert total(env)==0

def test_budget_survives_new_engine_and_rollback_is_atomic(env):
    cfg=PublicConfig.from_env()
    now=datetime(2026,9,15,12,1,tzinfo=timezone.utc)
    # A browser's third slot is its limit. Other scopes are not consumed by denial.
    for _ in range(3):env.reserve('one','net',now)
    assert total(env)==3
    fresh=DemoBudget(create_engine(cfg.database_url),cfg)
    with pytest.raises(PublicAccessError):fresh.reserve('one','net',now)
    assert total(env)==3
    fresh.reserve('two','net',now)
    assert total(env)==4
    fresh.engine.dispose()

def test_daily_budget_and_new_day(env):
    cfg=PublicConfig('test'*16,'https://testserver','sqlite://',daily=2,hourly=10)
    b=DemoBudget(env.engine,cfg)
    now=datetime(2026,9,15,12,tzinfo=timezone.utc)
    b.reserve('one','net-a',now);b.reserve('two','net-b',now)
    with pytest.raises(PublicAccessError) as e:b.reserve('three','net-c',now)
    assert e.value.retry_after==43201 and e.value.status==429
    b.reserve('three','net-c',now+timedelta(days=1))
    assert total(b)==3

def test_anonymous_cookie_rotation_does_not_bypass_network_budget(app,env):
    for i in range(6):
        with client(app[0]) as c:
            # Wait for each controlled job to free the local two-worker slots.
            r=send(c,prepare(c),TRT+'\nAdditional detail '+str(i))
            assert r.status_code in (200,202)
        time.sleep(.02)
    with client(app[0]) as c:
        r=send(c,prepare(c),TRT+'\nNew seventh version')
        assert r.status_code==429 and r.headers.get('retry-after')
    assert total(env)==6

def test_railway_uses_edge_real_ip_not_forwarded_chain():
    from starlette.requests import Request
    cfg=PublicConfig('test'*16,'https://testserver','postgres://test',railway=True)
    def request(real,forwarded='9.9.9.9'):
        return Request({'type':'http','method':'GET','path':'/','headers':[(b'x-real-ip',real.encode()),(b'x-forwarded-for',forwarded.encode())]})
    assert cfg.network(request('192.0.2.1'))==cfg.network(request('192.0.2.1','8.8.8.8'))
    assert cfg.network(request('2001:db8::1'))==cfg.network(request('2001:db8::2'))
    with pytest.raises(PublicAccessError):cfg.network(request(''))
    with pytest.raises(PublicAccessError):cfg.network(request('1.1.1.1,2.2.2.2'))

def test_only_operational_counters_are_stored(env):
    env.reserve('not-a-source','private-network-key')
    assert set(counters.c.keys())=={'bucket','attempts','expires_at'}
    with env.engine.connect() as cx:rows=cx.execute(select(counters)).all()
    assert all('private-network-key' not in str(r) or 'network:' in r.bucket for r in rows)
    assert all(TRT not in str(r) and '192.0.2.1' not in str(r) for r in rows)

def test_concurrent_postgres_admission_is_bounded():
    url=os.getenv('RNSREPO_TEST_DATABASE_URL')
    if not url:pytest.skip('requires real PostgreSQL test service')
    from database.db import normalise_database_url
    engine=create_engine(normalise_database_url(url))
    cfg=PublicConfig('postgres-test'*4,'https://testserver',url,daily=5,hourly=5)
    b=DemoBudget(engine,cfg);b.initialise()
    with engine.begin() as cx:cx.execute(counters.delete())
    now=datetime(2026,9,15,12,tzinfo=timezone.utc)
    def reserve(i):
        try:b.reserve(str(i),str(i),now);return True
        except PublicAccessError:return False
    with ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(reserve,range(24)))
    assert sum(results)==5 and total(b)==5
    engine.dispose()
