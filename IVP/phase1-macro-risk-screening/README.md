# Phase 1 — Macro-Risk Screening & Priority Queue

> Part of the [Landslide EWP build guide](README.md). Safety-critical: every threshold below is a placeholder for calibration and expert sign-off.

## At a glance

| | |
|---|---|
| **Goal** | Decide where scarce sensors and drone time go, issue regional rain-driven advisories, and expose where the system is blind, without ever treating unobserved terrain as safe |
| **Scale** | 100s–1000s km²; unit of analysis = slope unit; inputs at 10–30 m |
| **Inputs** | DEM, geology, land cover, exposure, landslide inventory, Sentinel-1/2, rainfall (gauge + satellite + radar + forecast), seismic and fire feeds |
| **Outputs** | Priority queue, hazard/risk/runout layers, regional advisory matrix, `UNKNOWN` masks, audit samples |
| **Cadence** | Rain hourly · InSAR per new acquisition · queue weekly + event-driven · static features on data change |
| **Consumed by** | Phase 2A (site selection), 2B (mission queue), 3 (advisories, runout footprints) |
| **Depends on** | M0 data audit, inventory, decisions D1–D3 and D6 |

## 1. Purpose, scope, invariants

Phase 1 answers three questions for the whole region:
1. **Where** are slope units most likely to fail, and who is downslope? → priority queue
2. **Is today's rain enough to matter?** → regional advisory matrix
3. **Where are we blind?** → `UNKNOWN` masks and re-acquisition tasks

**Non-goals:** time-to-failure, site-scale stability analysis, crack-scale analysis, any public alert.

**Invariants (each has a test, §9)**
- **I1** No hard "0 % risk" class. Every unit gets a score *and* a `data_status`.
- **I2** Missing or low-quality data ⇒ `UNKNOWN`, never "safe".
- **I3** Train and deploy on the same DEM resolution and the same feature definitions.
- **I4** Scores are calibrated and carry uncertainty; cut-offs come from a recall target.
- **I5** Every output traces to a `run_id`, code version and input snapshot.

## 2. Terminology

| Term | Meaning in this phase | Output |
|---|---|---|
| Susceptibility `S` | Static spatial likelihood per slope unit and process class; calibrated probability-like score | `unit_scores` |
| Trigger state | Rainfall / seismic / change context relative to calibrated thresholds | `regional_advisories` |
| Hazard `H` | `S`, raised to at least `h_active` when an ADA (active deformation) is present | `queue_items.scores` |
| Exposure `E`, Vulnerability `V` | Elements inside the unit and its runout footprint; class damage factor | `exposure_*` |
| Risk `R = H × E × V` | Used to **rank** the queue only. Alerts use trigger state and Phase 2A data, never `R` | `queue_items` |

## 3. Interfaces

**Inputs**

| Layer | Source options | Native resolution / latency | Used for |
|---|---|---|---|
| DEM | National LiDAR DTM (best); Copernicus GLO-30; FABDEM (check licence: non-commercial); ALOS AW3D30; SRTM | 1–30 m, static | Slope, curvature, slope units, runout |
| Sentinel-1 IW SLC (asc + desc) | Copernicus / ASF | ~5×20 m single-look; 6–12 day revisit | InSAR deformation |
| Sentinel-2 L2A | Copernicus | 10/20 m; ~5 day | Land-cover change, burn scars, masks, optical offset tracking |
| L-band SAR (optional) | NISAR where available, ALOS-2 | tens of m; days–weeks | Vegetated terrain; `UNKNOWN` re-acquisition |
| Rainfall | Gauges (hourly), IMERG (~0.1° ≈ 10 km, hours latency), radar if available, NWP forecast | hourly | Triggers, antecedent index |
| Geology | National survey: lithology, strike/dip, faults; modelled soil depth | map-scale, static | Lithology rating, kinematic index |
| Land cover | ESA WorldCover (10 m) or national | static + change | Context features |
| Seismic / fire | National network or ShakeMap-type grids; burn-area products | event-driven | Re-scoring triggers |
| Inventory | Polygons: type, date range, source, positional accuracy, **completeness polygons** | static | Training and validation |
| Exposure | OSM + open building footprints, WorldPop/GHSL or census, roads/rail, critical facilities | yearly | Exposure, vulnerability |

**Outputs:** `QueueItem` (root README §5), COG layers (`S`, `H`, `R`, runout probability), vector tiles, `RegionalAdvisory` messages, `UNKNOWN` masks.

## 4. Architecture

```
 STATIC (on data change)                  DYNAMIC (hourly → monthly)
 ┌──────────────────────────┐   ┌───────────────────────────────────────────────┐
 │ DEM → slope units        │   │ Rain: gauges+IMERG+radar+NWP → fusion         │
 │ geology · land cover     │   │        → API · I–D exceedance → matrix        │
 │ exposure · inventory     │   │ Sentinel-1 (asc+desc) → InSAR → ADA per unit  │
 └────────────┬─────────────┘   │ Sentinel-2 → change · burn · masks            │
              │                 │ Seismic / fire feeds → event triggers         │
              ▼                 └─────────────────────┬─────────────────────────┘
   Feature factory: value + quality per unit          │
              ▼                                       ▼
   Susceptibility model (calibrated S) ──► Hazard H (S + active deformation)
              ▼                                       │
   Runout / propagation ─► footprints ─► exposure in footprint
              └──────────────────┬────────────────────┘
                                 ▼
             Data-quality & UNKNOWN logic ─► Risk R = H × E × V
                                 ▼
   PRIORITY QUEUE (lanes: INSTRUMENT · DRONE_BASELINE · RESCREEN · AUDIT)
        │ queue items                          │ RegionalAdvisory (rain matrix)
        ▼                                      ▼
   Phases 2A / 2B / 3                       Phase 3
```

## 5. Build guide

### 5.1 DEM and slope units
1. Pick the DEM (D6). Record resolution, vertical accuracy, version, licence. Never resample silently.
2. Reproject to the metric CRS **before** any derivative. Keep raw and hydrologically conditioned DEMs.
3. Delineate slope units with `r.slopeunits` (GRASS add-on): half-basins bounded by drainage and ridgelines. Tune flow-accumulation threshold, minimum circular variance and min/max area so unit size matches the landslide size distribution.
4. Freeze `unit_id`s. Re-delineate only when the DEM changes, and write an ID crosswalk table.

**Check:** no gaps/overlaps; visual QA in three pilot areas; median inventoried landslide area vs unit area reported.

### 5.2 Static features
Compute per unit (mean, std, p10/p50/p90 for continuous layers; area fractions for categorical):

- Slope (Horn), aspect, plan/profile curvature, relative relief, TWI, flow accumulation
- Distance to streams, roads (cut slopes), faults; mean annual rainfall; seismic hazard (PGA)
- Lithology rating (lookup table authored with a geologist, versioned); soil-depth proxy (modelled; mark low confidence)
- Land cover and canopy-change history
- **Kinematic-feasibility index** (replaces "joint-to-slope aspect ratio"): share of slope-facing area where a mapped discontinuity set can daylight, e.g. for planar sliding: discontinuity dip < slope dip and dip direction within about ±20° of the slope dip direction (Markland-type test). Wedge and toppling tests where data allow. Where no attitudes exist, set `quality = UNKNOWN`; do not impute silently. Site-scale joint sets come from Phase 2B point clouds.

```python
# Horn (1981) 3x3 finite differences == Sobel / (8 * cell_size). Work in a metric CRS.
dz_dx = ((z3 + 2*z6 + z9) - (z1 + 2*z4 + z7)) / (8 * dx)
dz_dy = ((z7 + 2*z8 + z9) - (z1 + 2*z2 + z3)) / (8 * dy)
slope_deg = degrees(atan(sqrt(dz_dx**2 + dz_dy**2)))
```

### 5.3 Exposure and vulnerability layers
- Sources: building footprints, population grid, roads/rail, critical facilities (schools, health, power, water).
- **Exposure of a unit counts elements inside the unit and inside its runout footprint (§5.5).**
- `E = norm( w_p·log(1+pop) + w_b·log(1+buildings) + w_c·critical + w_r·road_km )`, weights set with the authority.
- `V` by element class (e.g. building type); default `1.0` when unknown (conservative).
- Aggregate to units; protect household-level data.

### 5.4 Inventory and susceptibility model
1. **Inventory:** polygons with type, date range, source, positional accuracy. Add **completeness polygons** (where mapping was actually done). Train on source-area (scarp) polygons rather than full runout.
2. **Labels:** per process class (D1): unit contains ≥ 1 source area. **Negatives only from complete areas**, never from unmapped ones.
3. **Validation split:** spatial block CV (block size ≥ spatial-autocorrelation range) plus hold-out by event where possible. Random CV is not accepted.
4. **Models:** logistic regression baseline → GAM → random forest / XGBoost. Choose by spatial-CV metrics. Keep the interpretable baseline for comparison.
5. **Calibration:** isotonic or Platt on out-of-fold predictions; reliability diagram per region.
6. **Metrics:** ROC-AUC, PR-AUC, success-rate curve, **recall at the operating point**, Brier score. Operating point = smallest flagged area meeting recall target R (D3). The flagged area is an *outcome* to budget for, not an input.
7. **Explainability:** SHAP; geologist reviews top drivers; remove leaky features (distance to inventory, post-event land cover).
8. **Uncertainty:** bootstrap or quantile intervals → `s_lo`, `s_hi`.
9. Log every run in MLflow with data hashes.

### 5.5 Runout / propagation
Purpose: flat ground below sources inherits hazard; exposure is counted inside footprints.

- **Regional method (empirical, non-dynamic):** source cells (S above a source threshold) → multiple-flow-direction spreading with persistence → stopped by an energy-line (angle of reach / friction angle). Flow-R implements this. As far as we know it is a MATLAB-runtime desktop tool, so decide how to wrap it headless, or use an open alternative: `r.avaflow`, or a short, auditable Python MFD + angle-of-reach implementation.
- Calibrate angle of reach / friction parameters **per process class** on mapped deposits (footprint overlap, ROC). Rockfall, debris flow and large deep-seated slides need different parameters.
- Outputs: `runout_prob` COG, `runout_footprints` polygons at probability threshold `p_ro`, unit-to-receiving-cell table.
- Dynamic models (flow depth, velocity, impact) are site-scale tasks after Phase 2B, not part of Phase 1.

### 5.6 Rainfall fusion and regional trigger matrix
1. **Fuse** gauges (QC'd, hourly) + IMERG + radar (if available) into a bias-corrected hourly grid (quantile mapping or kriging with external drift). Evaluate on held-out gauges. IMERG alone is ~10 km and biased in mountains.
2. **Forecast:** add NWP accumulations (next 6–72 h) from the national met service or a global model, for lead time. Track forecast skill.
3. **Features:** rolling sums (1, 3, 6, 24, 72 h), antecedent index with **calibrated** window/decay (do not hard-code 7 days), event duration and intensity.
4. **Thresholds:** intensity–duration curves per rainfall zone. Published curves (e.g. Caine 1980; Guzzetti et al. 2008) are priors only. Calibrate on local event-rainfall pairs, **including non-event days**; report POD and false-alarm ratio.
5. **Regional matrix** (illustrative: calibrate):

| Susceptibility class \ rain class | NORMAL | WATCH | EXCEEDED | EXTREME |
|---|---|---|---|---|
| LOW | – | – | ADVISORY | ADVISORY |
| MODERATE | – | ADVISORY | ADVISORY | WARNING_CANDIDATE |
| HIGH | – | ADVISORY | WARNING_CANDIDATE | WARNING_CANDIDATE |
| VERY_HIGH | – | ADVISORY | WARNING_CANDIDATE | WARNING_CANDIDATE |

   Outputs go to Phase 3 as `RegionalAdvisory` **candidates**. Phase 3 decides.
6. **Event triggers beyond rain:** earthquake (ground motion above threshold), wildfire burn area, rapid land-cover change → force re-scoring of affected units and queue promotion.

### 5.7 Deformation (InSAR + offset tracking)
1. Acquire Sentinel-1 IW SLC, **ascending and descending separately**. Require `min_scenes` (placeholder: 20–30) per geometry before velocities are `OK`; fewer → `DEGRADED`.
2. Process with **one** chain (the source lists ISCE3 and SNAP for the same step): ISCE2 `stackSentinel` (or ASF HyP3 on-demand) → MintPy SBAS; PS/DS processing (StaMPS or MiaplPy) for vegetated/mixed terrain. Pin versions.
3. Corrections: tropospheric (ERA5 / GACOS), DEM error, reference point on stable ground; SNAPHU unwrapping with closure checks.
4. Masks: temporal coherence (MintPy default 0.7), layover/shadow, low sensitivity to the slope direction, wet snow, water.
5. Decompose into linear trend + annual/semi-annual harmonics so seasonal soil-moisture swelling is not mistaken for sliding.
6. **Project LOS to the downslope direction** using ascending + descending (assumes motion parallel to the slope surface). Drop pixels with a small projection factor. North–south motion remains poorly observed.
7. **Significance:** pixel flagged if `|v_slope| > k·σ_v` (k from calibration). **ADA** = cluster of ≥ N coherent flagged pixels. Mask known non-landslide deformation (groundwater subsidence, mining, construction).
8. **Fast movers:** offset tracking on Sentinel-2 (COSI-Corr or autoRIFT) and Sentinel-1 amplitude. With 10 m pixels expect to see only about ≥ 0.5–1 m between epochs. It complements InSAR; it does not replace it.
9. Aggregate per unit: coverage %, velocity statistics, ADA flag, trend change → `deformation` block of the queue item.
10. **Known limits (feed `UNKNOWN`, §5.9):** line-of-sight only; blind in layover/shadow; decorrelates over vegetation (C-band); aliases when motion approaches a fraction of the ~2.8 cm half-wavelength per revisit. L-band is the re-acquisition path for vegetated terrain.

### 5.8 Optical layers (Sentinel-2) — previously ingested but unused
- Cloud/shadow masks (scene classification or s2cloudless), compositing, snow mask.
- Change detection: deforestation, burn scars (dNBR), new roads and cut slopes → re-scoring triggers.
- NDVI and land-cover class as **context features** in the model, never as a hard gate.
- Candidate new landslide scars from change detection → analyst confirmation → inventory.

### 5.9 Data quality and `UNKNOWN` logic
Each feature carries `(value, quality)` with quality ∈ {`OK`, `DEGRADED`, `UNKNOWN`} and reason codes. Unit `data_status` = worst quality among the **critical features** listed in config.

| Feature | `UNKNOWN` if | `DEGRADED` if |
|---|---|---|
| Deformation | coverage < `c_min` % of unit area, or < `n_min` scenes, or low sensitivity | coverage between `c_min` and `c_ok`, or one geometry only |
| Optical change | no clear observation within `w` days | single clear observation |
| Rainfall | all sources stale > `h` hours | one source stale or bias-flagged |
| Structure | no attitude measurements in unit | sparse measurements |

**Handling:** static susceptibility is still computed (static features exist). Uncertainty widens when a critical feature is `UNKNOWN`. `UNKNOWN` **never lowers rank**. High `S` or high `E` with `UNKNOWN` deformation ⇒ lane `RESCREEN`.

**Re-acquisition ladder** (each step has an owner and SLA): (1) other geometry or longer stack → (2) L-band → (3) corner reflectors / GNSS → (4) drone LiDAR baseline (Phase 2B) → (5) field visit.

**Invariant test:** for any input, `data_status == UNKNOWN ⇒ lane != NONE`.

### 5.10 Risk scoring and priority queue
```
H = S                       if no ADA
H = max(S, h_active)        if ADA present            # h_active configured, expert-set
R = H × E × V               # ranking only
```
| Lane | Rule (placeholders) | Next step |
|---|---|---|
| `INSTRUMENT` | top-N by `R`, `E ≥ e_min`, and (ADA or `S ≥ s_high`) | Phase 2A §4.1, expert confirmation required |
| `DRONE_BASELINE` | `R ≥ r_drone` or ADA present | Phase 2B baseline mission |
| `RESCREEN` | `UNKNOWN` and (`S ≥ s_med` or `E ≥ e_med`) | re-acquisition ladder |
| `AUDIT` | stratified random sample (`x` % per cycle) of `NONE` units | inspect; estimates the miss rate |
| `NONE` | everything else | passive monitoring |

- **Capacity-aware:** lane quotas from `capacity.yaml` (drone-days, instrument budget).
- **Hysteresis:** lane changes need persistence over ≥ `m` cycles unless an event trigger fires.
- **Audit loop:** audit outcomes feed recalibration and a reported miss-rate estimate.

### 5.11 Orchestration and cadence

| DAG | Schedule | Tasks |
|---|---|---|
| `static_features` | on data change | DEM prep, slope units, features, exposure |
| `susceptibility_train` | quarterly / manual | train, calibrate, register model |
| `susceptibility_score` | weekly | score units, runout, intervals |
| `rain_fusion` + `rain_matrix` | hourly | fuse, accumulations, matrix, publish advisories |
| `insar_ingest` / `insar_timeseries` | per new scene / monthly | download, process, invert, project, ADA |
| `optical_change` | per new tile | masks, change detection |
| `event_triggers` | event-driven | quake / fire → re-score |
| `queue_build` | weekly + on trigger | scoring, lanes, audit sample, publish |

Freshness SLIs: rain feed age, last Sentinel-1 scene age, queue age. Staleness raises an **ops** alert (Phase 3), never a public one.

## 6. Configuration (excerpt)

```yaml
region: R01
crs_metric: EPSG:326XX              # UTM zone for the region
dem: {source: national_lidar_or_glo30, resolution_m: 30, version: v1, licence_checked: true}
slope_units: {tool: r.slopeunits, thresh: null, cvmin: null, areamin_m2: null, areamax_m2: null}
processes: [shallow_debris, rockfall, deep_seated]          # D1
susceptibility:
  model: xgboost                    # baseline: logistic
  cv: {type: spatial_block, block_km: null, folds: 5}
  calibration: isotonic
  recall_target: null               # D3
rainfall:
  sources: [gauges, imerg, radar, nwp]
  accumulations_h: [1, 3, 6, 24, 72]
  api: {window_d: null, decay: null}                        # calibrate
  id_threshold: {zones: [], prior: caine1980, calibrated: false}
insar:
  min_scenes_per_geometry: 25
  min_temporal_coherence: 0.7
  v_sig_k: null
  ada_min_pixels: null
unknown:
  deformation: {min_coverage_pct: null, min_scenes: 25}
  optical: {max_gap_days: null}
  rainfall: {max_stale_h: null}
queue:
  lanes:
    INSTRUMENT: {max_n: null}
    DRONE_BASELINE: {max_n: null}
    RESCREEN: {max_n: null}
    AUDIT: {sample_pct: null}
  hysteresis_cycles: 2
```

## 7. Data model (PostGIS + TimescaleDB)

| Table | Key columns |
|---|---|
| `slope_units` | `unit_id` PK, `geom`, `area_m2`, `dem_version`, `params` |
| `unit_features` | `unit_id`, `feature`, `value`, `quality`, `run_id`, `computed_at` |
| `inventory` / `inventory_completeness` | `landslide_id`, `geom`, `type`, `date_from/to`, `source`, `pos_acc_m` / `area_id`, `geom`, `period` |
| `exposure_elements` | `element_id`, `geom`, `class`, `weight`, `source` |
| `model_runs`, `unit_scores` | `run_id`, `model`, `data_hash`, `metrics` / `unit_id`, `process`, `s`, `s_lo`, `s_hi` |
| `runout_footprints` | `source_unit_id`, `process`, `geom`, `p_threshold`, `run_id` |
| `deformation_units`, `ada_polygons` | `unit_id`, `coverage_pct`, `v_mm_yr`, `v_sigma`, `ada`, `status` / `ada_id`, `geom` |
| `rain_grid` (hypertable) | `ts`, `cell_id`, `mm_h`, `source_mix`, `quality` |
| `regional_advisories` | `advisory_id`, `area_id`, `ts`, `level`, `matrix_cell` |
| `queue_items`, `audit_samples` | `unit_id`, `run_id`, `lane`, `rank`, `risk`, `data_status`, `reasons` / `sample_id`, `drawn_at`, `outcome` |

## 8. Repository layout

```
phase1-macro-risk-screening/
├── README.md
├── config/            # region.yaml, capacity.yaml, thresholds/
├── dags/              # Airflow DAGs
├── src/ewp_p1/
│   ├── terrain/       # DEM prep, slope units, Horn derivatives
│   ├── features/      # static, exposure, optical
│   ├── models/        # train, calibrate, score, explain
│   ├── runout/
│   ├── rain/          # fusion, API, I–D matrix
│   ├── insar/         # wrappers, QC, projection, ADA
│   ├── quality/       # UNKNOWN logic
│   └── queue/         # scoring, lanes, audit sampling
├── sql/               # DDL, migrations
├── tests/             # unit, invariants, golden runs
└── notebooks/         # EDA only; never part of the pipeline
```

## 9. Testing and validation

**Automated tests**
- Horn slope on a synthetic 30° plane returns 30.0° ± 0.05° (regression test against the un-normalised Sobel mistake).
- LOS→downslope projection with known geometries; sign conventions.
- **Invariants:** `UNKNOWN ⇒ lane != NONE` (property-based); no unit without `data_status`.
- Same inputs + seed ⇒ identical output hash.
- Contract tests: every `QueueItem` validates against `contracts/queue_item.schema.json`.
- Spatial-leakage test: no unit in both train and test blocks.

**Validation studies**
- Spatial CV and held-out-event metrics; calibration curves per region.
- **Retrospective "would-have-flagged":** for each historical landslide, was its unit in `INSTRUMENT`, `DRONE_BASELINE` or `RESCREEN` before the event?
- InSAR vs GNSS/inclinometer where available; noise floor on known-stable terrain.
- Rain fusion skill vs held-out gauges; I–D thresholds with POD / false-alarm ratio.
- Audit-sample miss-rate estimate with confidence interval.

## 10. Acceptance criteria

- [ ] Recall ≥ R (D3) on held-out spatial blocks, with the flagged-area fraction reported
- [ ] Reliability curves within agreed tolerance in every region
- [ ] Retrospective "would-have-flagged" ≥ target for historical events
- [ ] `UNKNOWN` invariant tests green; no silent "safe"
- [ ] InSAR noise floor documented; GNSS cross-check within tolerance
- [ ] Rain fusion skill documented; I–D thresholds calibrated with POD/FAR
- [ ] Freshness SLIs live; queue age ≤ 7 days
- [ ] Contracts validated by Phase 2/3 consumers; audit trail per run

## 11. Failure modes

| Failure | Effect | Mitigation |
|---|---|---|
| Incomplete inventory labelled "stable" | Model learns wrong negatives | Completeness polygons; negatives only from complete areas; audit sampling |
| DEM resolution mismatch between training and deployment | Slope distribution shift | Same DEM/feature versions; tests |
| InSAR decorrelation / atmosphere | False positives or blindness | Coherence masks; ADA clustering; `UNKNOWN`; L-band |
| Rain feed outage or bias | Missed / false advisories | Multi-source fusion; staleness alerts; gauge fallback |
| Spatial leakage in CV | Optimistic metrics | Block CV; leakage test |
| Drift (land use, climate) | Calibration decay | Scheduled retraining; event re-scoring; calibration monitoring |
| Queue exceeds capacity | Backlog | Lane quotas; hysteresis; capacity-aware selection |
| Flow-R packaging | Pipeline stalls | Wrapper or open alternative decided early |

## 12. Open decisions (Phase 1)

- D1 process classes; D2 inventory source and completeness; D3 recall target; D6 DEM and licence (root README §9)
- Lane thresholds (`e_min`, `r_drone`, `s_high`, …) and who approves them
- Whether regional advisories use administrative polygons or slope-unit clusters
