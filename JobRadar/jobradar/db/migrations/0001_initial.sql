-- 0001_initial.sql
-- Initial schema for JobRadar API

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Jobs table
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fingerprint_hash VARCHAR(64) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    company VARCHAR(255) NOT NULL,
    company_url TEXT,
    location VARCHAR(255) NOT NULL DEFAULT 'Remote',
    tags TEXT[] NOT NULL DEFAULT '{}',
    min_salary INTEGER,
    max_salary INTEGER,
    apply_url TEXT NOT NULL,
    source VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    posted_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for jobs
CREATE INDEX idx_jobs_fingerprint ON jobs(fingerprint_hash);
CREATE INDEX idx_jobs_company ON jobs(company);
CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_posted_at ON jobs(posted_at DESC);
CREATE INDEX idx_jobs_status_last_seen ON jobs(status, last_seen_at);
CREATE INDEX idx_jobs_tags ON jobs USING GIN(tags);

-- Source health tracking
CREATE TABLE source_health (
    source_id VARCHAR(100) PRIMARY KEY,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    last_success_at TIMESTAMPTZ,
    last_error TEXT,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Sync runs history
CREATE TABLE sync_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_type VARCHAR(20) NOT NULL,
    sources_total INTEGER NOT NULL,
    sources_succeeded INTEGER NOT NULL DEFAULT 0,
    sources_failed INTEGER NOT NULL DEFAULT 0,
    sources_disabled INTEGER NOT NULL DEFAULT 0,
    jobs_added INTEGER NOT NULL DEFAULT 0,
    jobs_updated INTEGER NOT NULL DEFAULT 0,
    jobs_expired INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX idx_sync_runs_started_at ON sync_runs(started_at DESC);