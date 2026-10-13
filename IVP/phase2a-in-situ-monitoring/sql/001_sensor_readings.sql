-- Phase 2A: Continuous In-Situ Monitoring Database Schema
-- Compatible with PostgreSQL 15+, TimescaleDB 2.10+

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 1. Sites Table
CREATE TABLE IF NOT EXISTS sites (
    site_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    region VARCHAR(32) NOT NULL,
    slope_unit_id VARCHAR(64) NOT NULL,
    mechanism VARCHAR(32) NOT NULL,
    tier VARCHAR(16) NOT NULL CHECK (tier IN ('TIER_A', 'TIER_B', 'TIER_C')),
    movement_trend_deg DOUBLE PRECISION,
    movement_plunge_deg DOUBLE PRECISION,
    owner VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Sensors Metadata Table
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id VARCHAR(64) NOT NULL,
    site_id VARCHAR(64) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    sensor_type VARCHAR(64) NOT NULL,
    channel VARCHAR(64) NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT true,
    is_reference BOOLEAN NOT NULL DEFAULT false,
    serial_no VARCHAR(64),
    installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (site_id, sensor_id)
);

-- 3. Sensor Readings Table (TimescaleDB Hypertable)
CREATE TABLE IF NOT EXISTS sensor_readings (
    ts TIMESTAMPTZ NOT NULL,
    site_id VARCHAR(64) NOT NULL,
    sensor_id VARCHAR(64) NOT NULL,
    channel VARCHAR(64) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    sigma DOUBLE PRECISION,
    quality SMALLINT NOT NULL DEFAULT 0,
    seq BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (sensor_id, channel, ts)
);
SELECT create_hypertable('sensor_readings', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_site_ts ON sensor_readings(site_id, ts DESC);

-- Continuous Aggregate: 1-hour readings summary
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_readings_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', ts) AS bucket,
    site_id,
    sensor_id,
    channel,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    STDDEV(value) AS stddev_value,
    COUNT(*) AS reading_count
FROM sensor_readings
GROUP BY bucket, site_id, sensor_id, channel
WITH NO DATA;

-- 4. Noise Floor Calibration Table
CREATE TABLE IF NOT EXISTS noise_floor (
    site_id VARCHAR(64) NOT NULL,
    sensor_id VARCHAR(64) NOT NULL,
    channel VARCHAR(64) NOT NULL,
    sigma_noise DOUBLE PRECISION NOT NULL,
    estimated_from TIMESTAMPTZ NOT NULL,
    estimated_to TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (site_id, sensor_id, channel)
);

-- 5. Versioned TARP Thresholds Table
CREATE TABLE IF NOT EXISTS site_thresholds (
    threshold_version VARCHAR(64) NOT NULL,
    site_id VARCHAR(64) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    tarp_config JSONB NOT NULL,
    signed_off_by VARCHAR(128) NOT NULL,
    active_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (site_id, threshold_version)
);

-- 6. Sensor Health Status Table
CREATE TABLE IF NOT EXISTS sensor_health (
    site_id VARCHAR(64) NOT NULL,
    sensor_id VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('HEALTHY', 'DEGRADED', 'FAILED')),
    battery_v DOUBLE PRECISION,
    last_seen_ts TIMESTAMPTZ NOT NULL,
    flatline_flag BOOLEAN NOT NULL DEFAULT false,
    spike_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (site_id, sensor_id)
);

-- 7. Inverse Velocity Module (IVM) Forecasts Table
CREATE TABLE IF NOT EXISTS ivm_results (
    forecast_id VARCHAR(64) PRIMARY KEY,
    site_id VARCHAR(64) NOT NULL,
    sensor_id VARCHAR(64) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) NOT NULL CHECK (status IN ('VALID', 'NOT_ACCELERATING', 'NO_CONVERGENCE', 'BELOW_NOISE_FLOOR', 'RAIN_PULSE')),
    predicted_tf TIMESTAMPTZ,
    tf_lower_window TIMESTAMPTZ,
    tf_upper_window TIMESTAMPTZ,
    validity VARCHAR(16) CHECK (validity IN ('LOW', 'MEDIUM', 'HIGH')),
    alpha DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    r2_score DOUBLE PRECISION,
    flags JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_ivm_site_ts ON ivm_results(site_id, evaluated_at DESC);

-- 8. Breach Events Table
CREATE TABLE IF NOT EXISTS breach_events (
    event_id VARCHAR(64) PRIMARY KEY,
    site_id VARCHAR(64) NOT NULL REFERENCES sites(site_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    proposed_level VARCHAR(16) NOT NULL CHECK (proposed_level IN ('ADVISORY', 'WARNING', 'CRITICAL')),
    triggers JSONB NOT NULL,
    ivm JSONB NOT NULL,
    rain_context JSONB NOT NULL,
    monitoring_status VARCHAR(16) NOT NULL CHECK (monitoring_status IN ('NOMINAL', 'DEGRADED', 'BLIND')),
    evidence_url TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_breach_events_site_level ON breach_events(site_id, proposed_level);
