# Phase 2B — Targeted Drone Inspection & 3D Change Detection

> Part of the [Landslide EWP build guide](README.md). Safety-critical: every gate and cadence below is a placeholder for calibration.

## At a glance

| | |
|---|---|
| **Goal** | Produce high-resolution 3D baselines and repeatable change maps that expose scarps, fractures, volume change and post-event damage, with quantified uncertainty |
| **Role** | Mapping, verification and evidence. **Not** real-time time-to-failure tracking (that is Phase 2A) |
| **Inputs** | Phase 1 queue lanes (`DRONE_BASELINE`, `RESCREEN`), Phase 2A breaches, event triggers, weather forecasts, permits |
| **Outputs** | DTM/DSM, orthophoto, point clouds, change rasters, scarp and discontinuity layers, QC reports, STAC items |
| **Cadence** | Baseline once per site, periodic revisits, event-driven verification |
| **Consumed by** | Phase 1 (inventory, structure, runout calibration), Phase 2A (site design, verification), Phase 3 (evidence) |
| **Depends on** | M0 permits scoping; decision D8; Phase 2A for breach-driven missions |

## 1. Purpose, scope, non-goals

- Reveal what satellites cannot: bare-earth scarps under canopy, fracture sets, centimetre-to-decimetre surface change.
- **Honest limits:** under dense canopy, ground returns are sparse, so a DTM resolves decimetre-to-metre features (scarps, benches), not 1–5 cm cracks. Crack-width tiers from the first design are not used.
- Drone change detection resolves changes only above its measured noise floor (typically a few centimetres). It cannot provide hourly displacement or IVM input.

**Non-goals:** time-to-failure (Phase 2A), regional screening (Phase 1), alerting (Phase 3).

## 2. Interfaces

| Direction | Data |
|---|---|
| In | `QueueItem` (polygon, lane, priority), `BreachEvent` verification requests, event triggers (rain exceedance, earthquake) |
| In | Weather forecast, airspace/permit data, crew and equipment availability |
| Out | `DroneProduct` STAC Items (root README §5) with assets: DTM COG, orthophoto COG, point cloud COPC, change COG, scarps GeoPackage, QC report |
| Out | Inventory candidates and runout/deposit measurements → Phase 1; joint-set data → Phase 1 and 2A; evidence → Phase 3 |

## 3. Architecture

```
 Queue item / breach / event trigger
        ▼
 Mission planner & scheduler (permits · weather · crew · batteries)
        ▼
 Field protocol (control + check points · base station · flight · on-site QC)
        ▼
 Upload (raw, immutable) ─► Processing
     LiDAR : PPK trajectory → strip adjustment → ground classification → DTM
     Photo : SfM/MVS → DSM + orthophoto
        ▼
 Co-register on stable areas ─► Change detection (DoD / M3C2 with LoD95) ─► Landform & fracture mapping
        ▼
 QC gates ─► Products (COG · COPC · GeoPackage · STAC) ─► Analyst review
        ▼
 Phase 1 (inventory, structure, runout) · Phase 2A (design, verification) · Phase 3 (evidence)
```

## 4. Mission types and cadence

| Type | Trigger | Purpose | Notes |
|---|---|---|---|
| `BASELINE` | New `INSTRUMENT` / `DRONE_BASELINE` queue item | Reference DTM, orthophoto, point cloud | Prefer dry season / leaf-off |
| `PERIODIC` | Schedule per tier (e.g. pre- and post-wet-season) | Change vs baseline | Cadence in config |
| `EVENT` | Rain exceedance, earthquake, Phase 2A breach | Verification, post-event damage and volume | **Fly only when safe**: weather and slope conditions permitting |
| `RESCREEN` | Phase 1 `RESCREEN` lane | Fill `UNKNOWN` gaps | DTM + scarp map |

Priority = queue rank × weather window × crew/battery availability.

## 5. Hardware, planning and dispatch

### 5.1 Payload choice by situation

| Situation | Preferred payload |
|---|---|
| Forest / dense canopy | Multi-return LiDAR |
| Open or bare terrain | RTK/PPK photogrammetry (LiDAR optional) |
| Night or low light | LiDAR only |
| Seepage mapping (optional) | Thermal, pre-dawn |

All platforms need RTK/PPK positioning, a base station (own or network RTK) and a documented weather envelope per airframe.

### 5.2 Mission planner (service)
Inputs: queue polygon, DEM, permits and no-fly zones, forecast (wind, gusts, precipitation, visibility, cloud base), crew, battery cycles.

Generates, per mission:
- Terrain-following altitude with minimum clearance
- Line spacing for target ground-point density (LiDAR) or GSD (photogrammetry); typical SfM overlap about 75–80 % forward, 65–70 % side
- Speed and sun-angle window
- Mission file in the vendor format (or MAVLink for open stacks) plus a pre-flight checklist

### 5.3 Scheduler and go/no-go
- Scoring: priority × weather window × crew. Go/no-go limits live in config per airframe.
- **If flights are grounded, the system does nothing "creative":** monitoring defaults to Phase 2A telemetry and satellite data, and the mission stays queued.
- Capacity model: drone-days per month, batteries per day, crews, travel time. Report backlog to Phase 1 so lane quotas stay realistic.

### 5.4 Regulatory and privacy
Permits (BVLOS, night, airspace), operator licensing and insurance, privacy rules for imaging populated areas, restrictions on mapping/export of high-resolution data. Keep a flight log. Decision D8 settles in-house vs contracted operations.

## 6. Field protocol

1. **Pre-visit:** weather/permit check, equipment test, mission upload, safety brief.
2. **Safety:** keep crews out of runout zones and from beneath unstable slopes; use remote placement where possible.
3. **Control:** place ground control points (GCPs) and **independent check points** on **stable ground** (≥ `n` of each, spread across the area, not used in the adjustment). Targets on the moving mass act as tracking/check markers, never as control.
4. **Base station:** log long enough for PPK; record coordinates and antenna height.
5. **Fly** and **on-site QC:** coverage map, point-density preview, image sharpness, GNSS fix status. Re-fly gaps before leaving.
6. **Metadata:** time, weather, sun angle, airframe, payload serials, operator.
7. **Upload** raw data to immutable storage with a manifest and checksums.

## 7. Processing pipeline

**7.1 LiDAR georeferencing:** PPK trajectory; boresight calibration; strip adjustment; report RMSE on check points.

**7.2 Ground classification and DTM:** PDAL (CSF or SMRF). Manual QC on sample tiles. Choose DTM cell size from ground density (rule of thumb: median ≥ 3–5 ground points per cell). Save a **ground-density raster** as a QC product. Expect decimetre-to-metre features under canopy.

**7.3 Photogrammetry:** OpenDroneMap (ODM) or equivalent SfM/MVS → dense cloud → DSM and orthophoto. (OpenSfM alone does not deliver dense surfaces.)

**7.4 Co-registration to baseline:** ICP or plane fitting on **pre-defined stable reference polygons** (reviewed once per site). Report residuals. Never register on the moving mass.

**7.5 Change detection**
- DEM of Difference with propagated level of detection: `LoD95 = 1.96 × sqrt(σ₁² + σ₂²)`
- **M3C2** (py4dgeo; or CloudCompare in batch mode) for 3D change; `LoD95` includes local roughness, point counts **and registration error**
- Image correlation on orthophotos for horizontal vectors when displacement exceeds a few centimetres
- Volume change from DoD cells above `LoD95` only

**7.6 Landform mapping:** terrain derivatives (multi-direction hillshade, slope, curvature, local relief model, sky-view factor / openness via the Relief Visualization Toolbox) → candidate scarps, lineaments, benches, closed depressions → **analyst review** → `scarps` layer with length, height and freshness class.

**7.7 Rock-slope discontinuities:** facet extraction from point clouds (CloudCompare Facets or DSE), stereonet, kinematic tests (planar, wedge, toppling) against the slope face → joint sets (dip, dip direction, spacing) for Phase 1 structure features and Phase 2A design.

**7.8 Post-event:** deposit mapping, volume, runout length and angle of reach → Phase 1 runout calibration; new inventory polygons with dates.

Orchestrate with Airflow/Prefect in containers on a workstation or cloud (GPU optional for dense matching). Raw data is immutable; every product records software versions.

## 8. Uncertainty and QC gates

| Metric | Gate (placeholder) | If it fails |
|---|---|---|
| Check-point RMSE (x, y, z) | ≤ `r_xy`, `r_z` | Product not released; re-process or re-fly |
| Strip alignment | ≤ `a_max` | Re-adjust or re-fly |
| Ground density / coverage | ≥ `g_min`; ≥ 98 % area | Re-fly gaps; flag low-density cells |
| Registration residual on stable areas | ≤ `s_max` | Review reference polygons |
| `LoD95` | ≤ target | Report as `WARN`; changes below LoD suppressed |

`qc_status` ∈ {`PASS`, `WARN`, `FAIL`}; `FAIL` blocks release. **Measure the real noise floor** with repeat flights over stable terrain; derive `LoD95` from that, not from manufacturer specifications.

## 9. Products and schemas

- Rasters as COG, point clouds as COPC, vectors as GeoPackage, each registered as a **STAC Item** (root README §5).
- Naming: `<site_id>_<UTC date>_<payload>_<product>`.
- Every product links to `site_id` / `slope_unit_id`, mission ID, software versions, QC report.
- Auto-generated report (PDF/HTML): coverage, QC metrics, change summary, volumes, uncertainty.

## 10. Review workflow

Analyst interpretation of scarps and change → second-person check → expert sign-off before a product is used as evidence in Phase 3 → confirmed features update the inventory and structural datasets in Phase 1.

## 11. Safety and regulatory checklist

- [ ] Permits valid for the area, altitude, BVLOS and night operations as needed
- [ ] Crew safety plan; exclusion zones; communications
- [ ] Weather limits enforced by the scheduler, not by judgement alone
- [ ] Privacy and data-handling rules documented
- [ ] Incident reporting and flight log

## 12. Configuration (excerpt)

```yaml
missions:
  cadence: {BASELINE: once, PERIODIC: {tier_A: null, tier_B: null}, EVENT: on_trigger}
planning:
  min_clearance_m: null
  lidar: {target_ground_ppm2: null, pulse_return_mode: multi}
  photo: {gsd_cm: null, overlap_fwd: 0.8, overlap_side: 0.7}
weather_limits: {wind_ms: null, gust_ms: null, precip: none, visibility_m: null}
qc:
  check_points_min: null
  rmse_xy_m: null
  rmse_z_m: null
  coverage_pct: 98
  lod95_target_m: null
stable_reference_polygons: per_site
```

## 13. Repository layout

```
phase2b-drone-inspection/
├── README.md
├── config/              # missions, planning, qc, sites
├── planner/             # mission generation, scheduler, go/no-go
├── pipelines/           # Airflow/Prefect DAGs: lidar, photo, change, landform
├── src/ewp_p2b/
│   ├── lidar/           # PPK, strip adjust, ground class, DTM
│   ├── photo/           # ODM wrappers, orthophoto
│   ├── register/        # stable-area ICP, residuals
│   ├── change/          # DoD, M3C2 (py4dgeo), image correlation, volumes
│   ├── landform/        # terrain derivatives, scarp candidates
│   ├── discontinuities/ # facets, stereonet, kinematic tests
│   ├── qc/              # gates, reports
│   └── stac/            # item builders
├── tests/
└── docs/field-protocol.md
```

## 14. Testing

- **Repeatability:** repeat flights over stable terrain → real noise floor and `LoD95`; documented per site.
- **Known-displacement test:** move a reference target a measured distance; recovered change must match within `LoD95`.
- **Synthetic pipeline tests:** injected offsets, strip misalignments and sparse-ground tiles must trigger the right QC gate.
- **Contract tests:** every STAC Item validates against the contract.
- **Dry-run missions:** planner output flown on a safe test site before first live use.

## 15. Acceptance criteria

- [ ] Repeat-flight `LoD95` meets target on stable terrain
- [ ] Check-point RMSE within gates for baseline and revisit missions
- [ ] QC gates automated; `FAIL` blocks release (verified by test)
- [ ] Products flow to Phase 1 (inventory, structure) and Phase 3 (evidence) via contracts
- [ ] Planner respects weather and permit constraints in test scenarios
- [ ] Permits, crews, insurance and safety plan in place

## 16. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Registration error masquerades as displacement | Stable-area registration, independent check points, `LoD95` including registration error |
| Sparse ground returns under canopy | Report ground-density map; claim only decimetre-scale features there |
| Weather grounds flights during high-risk periods | Phase 2A and satellites carry monitoring; missions queued for the first safe window |
| Illumination differences between photo epochs | Fixed time-of-day window; LiDAR where feasible |
| Capacity backlog | Capacity model feeds Phase 1 lane quotas |
| Regulatory delays | Start permits at M0; consider contracted operators (D8) |

## 17. Open decisions (Phase 2B)

- D8 operations model and permissions; payload and airframe selection
- Cadence per tier and per season; stable-reference definition per site
- Where processing runs (edge vs cloud) given data volumes and connectivity
