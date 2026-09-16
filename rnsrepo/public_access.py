"""Bounded anonymous demo access. No account, source persistence or public history."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
import hashlib
import hmac
import ipaddress
import os
import secrets
from urllib.parse import urlsplit

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import (MetaData, Table, Column, String, Integer, DateTime, delete)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from starlette.requests import Request

COOKIE = 'rnsrepo_browser'
COOKIE_PATH = '/api/v1/analyse'
SESSION_SECONDS = 3600
NAMESPACE = 'rnsrepo-public-v1'
metadata = MetaData()
# Operational counters only: no RNS text, generated copy, raw IP or document hashes.
counters = Table('rnsrepo_demo_limits', metadata,
    Column('bucket', String(180), primary_key=True),
    Column('attempts', Integer, nullable=False),
    Column('expires_at', DateTime(timezone=True), nullable=False))


class PublicAccessError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 503, retry_after: int = 60):
        self.code, self.message, self.status, self.retry_after = code, message, status, retry_after
        super().__init__(code)


def enabled() -> bool:
    return os.getenv('RNSREPO_PUBLIC_ENABLED', '').lower() in {'1', 'true', 'yes'}


def _limit(name: str, default: int, maximum: int) -> int:
    try:
        return min(maximum, max(1, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


@dataclass(frozen=True)
class PublicConfig:
    secret: str
    origin: str
    database_url: str
    railway: bool = False
    daily: int = 30
    hourly: int = 10
    network_daily: int = 12
    network_hourly: int = 6
    browser_ten_minutes: int = 3

    @classmethod
    def from_env(cls) -> 'PublicConfig':
        cfg = cls(os.getenv('RNSREPO_SESSION_SECRET', ''),
            os.getenv('RNSREPO_PUBLIC_ORIGIN', '').rstrip('/'),
            os.getenv('DATABASE_URL', ''), bool(os.getenv('RAILWAY_ENVIRONMENT_ID')),
            _limit('RNSREPO_DAILY_ATTEMPTS', 30, 100),
            _limit('RNSREPO_HOURLY_ATTEMPTS', 10, 30))
        u = urlsplit(cfg.origin)
        local = u.hostname in {'localhost', '127.0.0.1'}
        if (len(cfg.secret) < 32 or not u.netloc or u.path or u.query or u.fragment
                or u.username or u.password or not cfg.database_url
                or (u.scheme != 'https' and not (local and u.scheme == 'http' and not cfg.railway))
                or (cfg.railway and not cfg.database_url.startswith(('postgres:', 'postgresql:','postgresql+psycopg:')))
                or os.getenv('WEB_CONCURRENCY', '1') != '1'):
            raise PublicAccessError('DEMO_CONFIGURATION', 'The demo is temporarily unavailable. Your text is still here.')
        return cfg

    def digest(self, purpose: str, value: str) -> str:
        return hmac.new(self.secret.encode(), f'{NAMESPACE}:{purpose}:{value}'.encode(), hashlib.sha256).hexdigest()

    def signer(self) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(self.secret, salt=NAMESPACE,
                                      signer_kwargs={'digest_method': hashlib.sha256})

    def read_owner(self, token: str) -> str | None:
        if not token or len(token) > 500:
            return None
        try:
            owner = self.signer().loads(token, max_age=SESSION_SECONDS)
            if isinstance(owner, str) and len(owner) == 43 and all(c.isalnum() or c in '-_' for c in owner):
                return owner
        except (BadSignature, SignatureExpired):
            pass
        return None

    def prepare_session(self, request: Request) -> tuple[str, str, str]:
        owner = self.read_owner(request.cookies.get(COOKIE, '')) or secrets.token_urlsafe(32)
        return owner, self.signer().dumps(owner), self.digest('csrf', owner)

    def require_owner(self, request: Request, *, mutation: bool = False) -> str:
        owner = self.read_owner(request.cookies.get(COOKIE, ''))
        if not owner:
            raise PublicAccessError('DEMO_SESSION', 'Your browser session expired. Press Analyse to start again.', 403)
        if mutation:
            self.check_origin(request, mutation=True)
            if not hmac.compare_digest(request.headers.get('x-rnsrepo-token', ''), self.digest('csrf', owner)):
                raise PublicAccessError('DEMO_SESSION', 'Please submit the announcement from this page.', 403)
        return 'public:' + owner

    def check_origin(self, request: Request, *, mutation: bool = False) -> None:
        # Never derive the trusted origin from a client-supplied Host/forwarded header.
        incoming = request.headers.get('origin')
        site = request.headers.get('sec-fetch-site')
        if ((incoming is not None and incoming != self.origin) or
                site in {'cross-site', 'same-site'} or
                (mutation and incoming != self.origin) or
                request.headers.get('host', '') != urlsplit(self.origin).netloc):
            raise PublicAccessError('INVALID_ORIGIN', 'Please submit the announcement from this page.', 403)

    def network(self, request: Request) -> str:
        # Railway overwrites X-Real-IP at its HTTP edge. Do NOT parse X-Forwarded-For.
        # Private-network peers are trusted infrastructure, not public rate-limit users.
        value = request.headers.get('x-real-ip', '') if self.railway else (request.client.host if request.client else '')
        try:
            address = ipaddress.ip_address(value)
            if address.version == 6:
                value = str(ipaddress.ip_network(f'{address}/64', strict=False))
            else:
                value = str(address)
        except ValueError:
            raise PublicAccessError('DEMO_NETWORK', 'The demo could not verify this connection. Your text is still here.') from None
        return self.digest('network', value)


class DemoBudget:
    """Atomically reserve all applicable limits before admitting a model job.

    Reservations are pessimistic: failed jobs keep their slot, and no refunds or
    catch-up retries can push spending above the admitted-attempt budget. Counters
    survive deploys. This limits requests, not an OpenAI account's dollar invoice.
    """
    def __init__(self, engine, config: PublicConfig):
        self.engine, self.config = engine, config

    def initialise(self) -> None:
        metadata.create_all(self.engine)

    def reserve(self, owner: str, network: str, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour = now.replace(minute=0, second=0, microsecond=0)
        window = hour + timedelta(minutes=(now.minute // 10) * 10)
        cfg = self.config
        scopes = [
            ('global:day', '', day, timedelta(days=1), cfg.daily),
            ('global:hour', '', hour, timedelta(hours=1), cfg.hourly),
            ('network:day', network, day, timedelta(days=1), cfg.network_daily),
            ('network:hour', network, hour, timedelta(hours=1), cfg.network_hourly),
            ('browser:ten', cfg.digest('owner', owner), window, timedelta(minutes=10), cfg.browser_ten_minutes),
        ]
        insert = pg_insert if self.engine.dialect.name == 'postgresql' else sqlite_insert
        with self.engine.begin() as connection:
            # Bound retention; expires_at includes a grace day for rate-limit auditing.
            connection.execute(delete(counters).where(counters.c.expires_at < now))
            for scope, identity, start, duration, maximum in scopes:
                bucket = f'{scope}:{start.isoformat()}:{identity}'
                stmt = insert(counters).values(bucket=bucket, attempts=1, expires_at=start + duration + timedelta(days=1))
                stmt = stmt.on_conflict_do_update(index_elements=[counters.c.bucket],
                    set_={'attempts': counters.c.attempts + 1},
                    where=counters.c.attempts < maximum).returning(counters.c.attempts)
                if connection.execute(stmt).scalar_one_or_none() is None:
                    wait = max(1, int((start + duration - now).total_seconds()) + 1)
                    msg = ('The demo’s daily allowance has been reached. Try again after midnight UTC.'
                           if scope == 'global:day' else 'The demo’s usage limit has been reached. Please try again later.')
                    raise PublicAccessError('DEMO_LIMIT', msg + ' Your text is still here.', 429, wait)


@lru_cache(maxsize=1)
def budget() -> DemoBudget:
    from database.db import normalise_database_url
    from sqlalchemy import create_engine
    cfg = PublicConfig.from_env()
    url = normalise_database_url(cfg.database_url)
    args = {'connect_timeout': 5, 'options': '-c statement_timeout=5000 -c lock_timeout=3000'} if url.startswith('postgresql') else {'check_same_thread': False}
    engine = create_engine(url, connect_args=args, pool_pre_ping=True)
    instance = DemoBudget(engine, cfg)
    # Schema is created explicitly by pre-deploy, not by an anonymous request.
    return instance


@lru_cache(maxsize=1)
def build_fingerprint() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for name in ('api/rnsrepo_public.py', 'api/paste.py', 'api/paste_jobs.py',
                 'rnsrepo/public_access.py', 'rnsrepo/extractor.py', 'rnsrepo/citations.py', 'rnsrepo/sections.py', 'rnsrepo/schema.py', 'rnsrepo/validation.py', 'product/paste.py',
                 'frontend/analyse.html', 'frontend/assets/analyse.js',
                 'frontend/assets/analysis-card.js', 'frontend/assets/analyse.css',
                 'frontend/assets/analysis-card.css', 'frontend/assets/rnsrepo.css'):
        digest.update(name.encode()); digest.update((root / name).read_bytes())
    return digest.hexdigest()[:16]
