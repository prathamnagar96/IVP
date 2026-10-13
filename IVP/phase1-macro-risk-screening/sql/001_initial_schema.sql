-- Phase 1: Macro-Risk Screening Database Schema
-- Compatible with PostgreSQL 15+, PostGIS 3+, TimescaleDB 2.10+

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 1. Slope Units Table
CREATE TABLE IF NOT EXISTS slope_units (
    unit_id VARCHAR(64) PRIMARY KEY,
    geom GEOMETRY(Polygon, 4326) NOT NULL,
    geom_metric GEOMETRY(Polygon, 32633),
    area_m2 DOUBLE PRECISION NOT NULL,
    dem_version VARCHAR(64) NOT NULL,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_slope_units_geom ON slope_units USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_slope_units_geom_metric ON slope_units USING GIST(geom_metric);

-- 2. Unit Features Table
CREATE TABLE IF NOT EXISTS unit_features (
    unit_id VARCHAR(64) NOT NULL REFERENCES slope_units(unit_id) ON DELETE CASCADE,
    feature VARCHAR(64) NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    quality VARCHAR(16) NOT NULL CHECK (quality IN ('OK', 'DEGRADED', 'UNKNOWN')),
    reason VARCHAR(256),
    run_id VARCHAR(64) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (unit_id, feature, run_id)
);
CREATE INDEX IF NOT EXISTS idx_unit_features_run_id ON unit_features(run_id);
CREATE INDEX IF NOT EXISTS idx_unit_features_feature ON unit_features(feature);

-- 3. Landslide Inventory & Completeness Tables
CREATE TABLE IF NOT EXISTS inventory (
    landslide_id VARCHAR(64) PRIMARY KEY,
    geom GEOMETRY(Geometry, 4326) NOT NULL,
    type VARCHAR(32) NOT NULL,
    date_from DATE,
    date_to DATE,
    source VARCHAR(128) NOT NULL,
    pos_acc_m DOUBLE PRECISION,
    is_source_area BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_inventory_geom ON inventory USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_inventory_type ON inventory(type);

CREATE TABLE IF NOT EXISTS inventory_completeness (
    area_id VARCHAR(64) PRIMARY KEY,
    geom GEOMETRY(Polygon, 4326) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    mapping_source VARCHAR(128) NOT NULL,
    completeness_confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_inv_completeness_geom ON inventory_completeness USING GIST(geom);

-- 4. Exposure Elements Table
CREATE TABLE IF NOT EXISTS exposure_elements (
    element_id VARCHAR(64) PRIMARY KEY,
    geom GEOMETRY(Geometry, 4326) NOT NULL,
    element_class VARCHAR(64) NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    vulnerability_factor DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    source VARCHAR(64) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_exposure_elements_geom ON exposure_elements USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_exposure_elements_class ON exposure_elements(element_class);

-- 5. Model Runs and Susceptibility Scores
CREATE TABLE IF NOT EXISTS model_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    model_type VARCHAR(64) NOT NULL,
    model_version VARCHAR(32) NOT NULL,
    input_data_hash VARCHAR(128) NOT NULL,
    metrics JSONB NOT NULL,
    hyperparameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS unit_scores (
    unit_id VARCHAR(64) NOT NULL REFERENCES slope_units(unit_id) ON DELETE CASCADE,
    run_id VARCHAR(64) NOT NULL REFERENCES model_runs(run_id) ON DELETE CASCADE,
    process VARCHAR(32) NOT NULL,
    s DOUBLE PRECISION NOT NULL CHECK (s >= 0.0 AND s <= 1.0),
    s_lo DOUBLE PRECISION NOT NULL CHECK (s_lo >= 0.0 AND s_lo <= 1.0),
    s_hi DOUBLE PRECISION NOT NULL CHECK (s_hi >= 0.0 AND s_hi <= 1.0),
    scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (unit_id, run_id, process)
);
CREATE INDEX IF NOT EXISTS idx_unit_scores_run_id ON unit_scores(run_id);
CREATE INDEX IF NOT EXISTS idx_unit_scores_s ON unit_scores(s DESC);

-- 6. Runout Footprints Table
CREATE TABLE IF NOT EXISTS runout_footprints (
    footprint_id VARCHAR(64) PRIMARY KEY,
    source_unit_id VARCHAR(64) NOT NULL REFERENCES slope_units(unit_id) ON DELETE CASCADE,
    process VARCHAR(32) NOT NULL,
    geom GEOMETRY(Polygon, 4326) NOT NULL,
    p_threshold DOUBLE PRECISION NOT NULL,
    angle_of_reach_deg DOUBLE PRECISION NOT NULL,
    receiving_units JSONB NOT NULL DEFAULT '[]'::jsonb,
    run_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_runout_footprints_geom ON runout_footprints USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_runout_source_unit ON runout_footprints(source_unit_id);

-- 7. InSAR Deformation & Active Deformation Areas (ADA)
CREATE TABLE IF NOT EXISTS deformation_units (
    unit_id VARCHAR(64) NOT NULL REFERENCES slope_units(unit_id) ON DELETE CASCADE,
    run_id VARCHAR(64) NOT NULL,
    coverage_pct DOUBLE PRECISION NOT NULL CHECK (coverage_pct >= 0.0 AND coverage_pct <= 100.0),
    v_downslope_mm_yr DOUBLE PRECISION NOT NULL,
    v_sigma_mm_yr DOUBLE PRECISION NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('OK', 'DEGRADED', 'UNKNOWN')),
    ada BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (unit_id, run_id)
);
CREATE INDEX IF NOT EXISTS idx_deformation_units_ada ON deformation_units(ada);

CREATE TABLE IF NOT EXISTS ada_polygons (
    ada_id VARCHAR(64) PRIMARY KEY,
    unit_id VARCHAR(64) REFERENCES slope_units(unit_id) ON DELETE SET NULL,
    geom GEOMETRY(Polygon, 4326) NOT NULL,
    pixel_count INTEGER NOT NULL,
    mean_v_mm_yr DOUBLE PRECISION NOT NULL,
    max_v_mm_yr DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ada_polygons_geom ON ada_polygons USING GIST(geom);

-- 8. Rainfall Grid (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS rain_grid (
    ts TIMESTAMPTZ NOT NULL,
    cell_id VARCHAR(32) NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    mm_h DOUBLE PRECISION NOT NULL,
    source_mix VARCHAR(64) NOT NULL,
    quality VARCHAR(16) NOT NULL CHECK (quality IN ('OK', 'DEGRADED', 'STALE')),
    PRIMARY KEY (ts, cell_id)
);
SELECT create_hypertable('rain_grid', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_rain_grid_cell_ts ON rain_grid(cell_id, ts DESC);

-- 9. Regional Advisories
CREATE TABLE IF NOT EXISTS regional_advisories (
    advisory_id VARCHAR(64) PRIMARY KEY,
    area_id VARCHAR(64) NOT NULL,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level VARCHAR(32) NOT NULL CHECK (level IN ('NONE', 'ADVISORY', 'WARNING_CANDIDATE')),
    matrix_cell VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_regional_advisories_ts ON regional_advisories(ts DESC);

-- 10. Priority Queue Items and Audit Samples
CREATE TABLE IF NOT EXISTS queue_items (
    unit_id VARCHAR(64) NOT NULL REFERENCES slope_units(unit_id) ON DELETE CASCADE,
    run_id VARCHAR(64) NOT NULL,
    lane VARCHAR(32) NOT NULL CHECK (lane IN ('INSTRUMENT', 'DRONE_BASELINE', 'RESCREEN', 'AUDIT', 'NONE')),
    priority_rank INTEGER,
    risk DOUBLE PRECISION NOT NULL CHECK (risk >= 0.0 AND risk <= 1.0),
    data_status VARCHAR(16) NOT NULL CHECK (data_status IN ('OK', 'DEGRADED', 'UNKNOWN')),
    scores JSONB NOT NULL,
    deformation JSONB NOT NULL,
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    runout JSONB NOT NULL DEFAULT '{}'::jsonb,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (unit_id, run_id)
);
CREATE INDEX IF NOT EXISTS idx_queue_items_lane_rank ON queue_items(lane, priority_rank);
CREATE INDEX IF NOT EXISTS idx_queue_items_data_status ON queue_items(data_status);

CREATE TABLE IF NOT EXISTS audit_samples (
    sample_id VARCHAR(64) PRIMARY KEY,
    unit_id VARCHAR(64) NOT NULL REFERENCES slope_units(unit_id) ON DELETE CASCADE,
    run_id VARCHAR(64) NOT NULL,
    drawn_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    audited_at TIMESTAMPTZ,
    audited_by VARCHAR(64),
    outcome VARCHAR(32) CHECK (outcome IN ('NO_ACTIVITY', 'FALSE_NEGATIVE_SOURCE', 'SIGNS_OF_CREEP', 'PENDING')),
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_samples_run ON audit_samples(run_id);
