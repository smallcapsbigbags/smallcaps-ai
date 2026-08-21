-- Smallcaps.ai AIM Intelligence — Pass 1 PostgreSQL schema
-- Railway Postgres is the production system of record. Existing static prototype
-- files remain untouched on this feature branch.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(24) NOT NULL UNIQUE,
    company_name VARCHAR(255) NOT NULL,
    isin VARCHAR(32) NOT NULL DEFAULT '',
    market VARCHAR(32) NOT NULL DEFAULT 'AIM',
    sector VARCHAR(128) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source_id VARCHAR(160) NOT NULL UNIQUE,
    published_at TIMESTAMPTZ NOT NULL,
    headline VARCHAR(500) NOT NULL,
    announcement_type VARCHAR(100) NOT NULL DEFAULT 'Other',
    source_url TEXT NOT NULL DEFAULT '',
    raw_text TEXT NOT NULL,
    categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_announcements_company_published
    ON announcements(company_id, published_at DESC);

CREATE TABLE IF NOT EXISTS analyst_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    announcement_id UUID NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
    impact_colour VARCHAR(16) NOT NULL CHECK (impact_colour IN ('green','amber','red','grey')),
    impact_score INTEGER NOT NULL CHECK (impact_score BETWEEN 1 AND 5),
    impact_level VARCHAR(16) NOT NULL CHECK (impact_level IN ('low','medium','high','critical')),
    headline VARCHAR(500) NOT NULL,
    takeaway TEXT NOT NULL,
    what_changed JSONB NOT NULL,
    analyst_view TEXT NOT NULL,
    supports_case JSONB NOT NULL DEFAULT '[]'::jsonb,
    challenges_case JSONB NOT NULL DEFAULT '[]'::jsonb,
    watch_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0.8 CHECK (confidence BETWEEN 0 AND 1),
    prompt_version VARCHAR(80) NOT NULL,
    model_version VARCHAR(120) NOT NULL,
    analysis_version VARCHAR(120) NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_analyst_runs_announcement_created
    ON analyst_runs(announcement_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_analyst_runs_one_current
    ON analyst_runs(announcement_id) WHERE is_current;

CREATE TABLE IF NOT EXISTS facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    announcement_id UUID NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
    analyst_run_id UUID NOT NULL REFERENCES analyst_runs(id) ON DELETE CASCADE,
    label VARCHAR(255) NOT NULL,
    metric VARCHAR(160) NOT NULL DEFAULT '',
    period VARCHAR(80) NOT NULL DEFAULT '',
    value VARCHAR(255) NOT NULL,
    unit VARCHAR(40) NOT NULL DEFAULT '',
    basis VARCHAR(32) NOT NULL CHECK (basis IN ('reported','calculated','not-disclosed','source-warning')),
    note TEXT NOT NULL DEFAULT '',
    comparator TEXT NOT NULL DEFAULT '',
    previous_value VARCHAR(255) NOT NULL DEFAULT '',
    information_status VARCHAR(32) NOT NULL DEFAULT 'new',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_facts_company_metric_period
    ON facts(company_id, metric, period, created_at DESC);

CREATE TABLE IF NOT EXISTS guidance_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    announcement_id UUID NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
    analyst_run_id UUID NOT NULL REFERENCES analyst_runs(id) ON DELETE CASCADE,
    metric VARCHAR(160) NOT NULL,
    period VARCHAR(80) NOT NULL DEFAULT '',
    value VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL,
    comparator TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_guidance_company_metric_period
    ON guidance_events(company_id, metric, period, created_at DESC);

CREATE TABLE IF NOT EXISTS management_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    announcement_id UUID NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
    analyst_run_id UUID NOT NULL REFERENCES analyst_runs(id) ON DELETE CASCADE,
    claim TEXT NOT NULL,
    target_date VARCHAR(80) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    outcome TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_claims_company_status
    ON management_claims(company_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS price_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    announcement_id UUID NOT NULL REFERENCES announcements(id) ON DELETE CASCADE,
    reaction_session VARCHAR(32) NOT NULL,
    previous_close DOUBLE PRECISION,
    open_price DOUBLE PRECISION,
    latest_price DOUBLE PRECISION,
    close_price DOUBLE PRECISION,
    return_1d DOUBLE PRECISION,
    return_5d DOUBLE PRECISION,
    return_20d DOUBLE PRECISION,
    currency VARCHAR(16) NOT NULL DEFAULT 'GBp',
    source VARCHAR(120) NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (announcement_id, reaction_session)
);

CREATE TABLE IF NOT EXISTS corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analyst_run_id UUID NOT NULL REFERENCES analyst_runs(id) ON DELETE CASCADE,
    field_path VARCHAR(255) NOT NULL,
    original_value JSONB,
    corrected_value JSONB,
    reason TEXT NOT NULL,
    corrected_by VARCHAR(120) NOT NULL DEFAULT 'owner',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_corrections_analyst_run
    ON corrections(analyst_run_id, created_at DESC);
