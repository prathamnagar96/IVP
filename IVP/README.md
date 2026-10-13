# Landslide Early Warning & Risk Platform — Build Guide (v2)

> **Safety-critical system.** Every numeric threshold, SLA and cut-off in this guide is a **placeholder for calibration**. Nothing here may drive a public alert until a qualified engineering geologist / geotechnical engineer and the responsible civil authority have signed off the site-specific values.

This guide turns the revised "continuous multi-scale risk engine" architecture into a buildable plan. Each phase has its own README.

| Phase | What it does | Cadence | Guide |
|---|---|---|---|
| **1 · Macro-risk screening & priority queue** | Ranks slope units by risk, issues regional rain-driven advisories, flags where the system is blind (`UNKNOWN`) | rain hourly · InSAR per acquisition · queue weekly + on events | `README-phase1-macro-risk-screening.md` |
| **2A · Continuous in-situ monitoring** | 24/7 measurement and early-warning logic on instrumented critical slopes | seconds to minutes | `README-phase2a-in-situ-monitoring.md` |
| **2B · Targeted drone inspection** | High-resolution 3D baselines, scarp/fracture mapping, change detection, post-event assessment | periodic + event-driven | `README-phase2b-drone-inspection.md` |
| **3 · Governance, validation & alerting** | Human-gated alert workflow, CAP broadcast, de-escalation, audit, feedback loop | real time | `README-phase3-governance-alerting.md` |

---

## 1. Scope

**In scope**
- Regional prioritisation of slope units by hazard, exposure and data gaps
- Continuous monitoring and early-warning logic on instrumented slopes
- Periodic / event-driven drone mapping as baseline and evidence
- Expert-validated, standards-based (CAP) alerting with audit and a feedback loop

**Non-goals**
- Guaranteeing detection of every failure
- Replacing expert judgement
- Machine-only public alerts (default mode; see decision D5)
- Running evacuations (the platform informs them)

## 2. System overview

```
   ┌──────────────────────────── PHASE 1 ─────────────────────────────┐
   │ DEM · geology · land cover · exposure · inventory                │
   │ Sentinel-1 InSAR · Sentinel-2 · rain (gauge+sat+radar+forecast)  │
   │ → susceptibility → runout → risk → UNKNOWN logic → PRIORITY QUEUE│
   └───────────┬───────────────────────────────┬──────────────────────┘
   regional rain advisories                    │ queue items
               │                 ┌─────────────┴──────────────┐
               │                 ▼                            ▼
               │        PHASE 2A in-situ (24/7)      PHASE 2B drone mapping
               │        GNSS · piezo · tilt · rain   LiDAR DTM · M3C2 · scarps
               │                 │ breach events              │ evidence products
               ▼                 ▼                            ▼
   ┌──────────────────────────── PHASE 3 ─────────────────────────────┐
   │ trigger → geotechnical expert → civil authority → CAP broadcast  │
   │ de-escalation · audit · feedback to Phases 1 and 2               │
   └──────────────────────────────────────────────────────────────────┘
```

## 3. Design principles

1. **Unobserved ≠ safe.** `UNKNOWN` is a first-class state and never ranks below "needs attention".
2. **Isolate the alerting plane.** Telemetry → rules → review → CAP runs on a small, highly available stack. Heavy analytics (InSAR, point clouds, ML training) can fail without touching it.
3. **Forecast only with instruments that can resolve the signal.** Drones map and verify; time-to-failure logic runs on continuous in-situ data.
4. **Humans decide public alerts** (default mode). Any pre-authorised automatic local action is an explicit authority decision (D5).
5. **Calibrate, then trust.** Scores are probabilistic and reliability-tested; thresholds come from recall / false-alarm targets and local data.
6. **Reproducible and auditable.** Every score, alert and approval traces to inputs, code version and a named person.

## 3a. Terminology (used identically in every phase)

| Term | Meaning |
|---|---|
| Susceptibility (S) | Spatial likelihood that a slope unit contains landslide source areas, given static conditions. No time dimension. |
| Hazard (H) | S combined with active-deformation evidence and trigger context |
| Exposure (E) | People, buildings, infrastructure inside the unit **and** its modelled runout footprint |
| Vulnerability (V) | Susceptibility of those elements to damage (class factor) |
| Risk (R) | H × E × V. Used for **ranking**, never for alerting |

## 4. Changes versus the source architecture

| # | Source architecture | Issue | Handled in |
|---|---|---|---|
| 1 | "Hazard × Exposure" with no exposure data; Sentinel-2 ingested but unused | Score cannot be computed as written | P1 §5.3, §5.8 |
| 2 | Susceptibility, hazard, risk used interchangeably; 0–1 score uncalibrated | Not interpretable as probability; not comparable across regions | P1 §2, §5.4, §5.10 |
| 3 | "Structural joint-to-slope face aspect ratio" | Not a standard measure; regional structural data is sparse | P1 §5.2; P2B §7 |
| 4 | Flow-R described as "3D kinematic" | Empirical raster propagation model, no flow dynamics; awkward to run headless | P1 §5.5 |
| 5 | IMERG as the rain feed | ~10 km, biased in mountains, no forecast | P1 §5.6 |
| 6 | `UNKNOWN` mentioned but not defined | Granularity and re-acquisition paths missing | P1 §5.9 |
| 7 | Inverse velocity = "true, physics-based" time-to-failure | Empirical; valid only for accelerating creep; no path for rapid-onset failures; no quantitative alert triggers | P2A §6–7 |
| 8 | Sensor stack lists instruments only | No telemetry, power, health monitoring or maintenance; "blind" must never mean "stable" | P2A §5, §8–9 |
| 9 | Expert SLA < 15 min; fallback "escalation path" | Needs a 24/7 rota; authority SLA, fail-safe direction, de-escalation and feedback undefined; rapid-onset hazards may leave < 15 min | P3 §3–5, §9 |
| 10 | openSfM, CloudCompare GUI for M3C2, ISCE3 + SNAP, no stream consumer or observability | Not automatable or redundant as listed | P1 §5.7; P2B §7; §8 below |
| 11 | No validation or rollout plan | — | §6 below |

## 5. Shared conventions and interface contracts

**Conventions**
- IDs: `slope_unit_id` (`SU-<region>-<seq>`), `site_id` (`SITE-<seq>`), `sensor_id`, `event_id` (UUID), `run_id` (`p1-<UTC timestamp>`).
- Time: UTC, ISO 8601. Store geometries in EPSG:4326; process in a metric UTM CRS (`EPSG:326XX` for the region).
- Units: SI. Displacement mm, velocity mm/day (in-situ) or mm/yr (InSAR), rainfall mm, angles in degrees.
- Status enums: `data_status` ∈ {`OK`, `DEGRADED`, `UNKNOWN`}; `monitoring_status` ∈ {`NOMINAL`, `DEGRADED`, `BLIND`}; `qc_status` ∈ {`PASS`, `WARN`, `FAIL`}.
- Contracts live in `contracts/` as JSON Schema; every producer and consumer validates against them in CI.

**QueueItem** (Phase 1 → 2A / 2B / 3)
```json
{
  "slope_unit_id": "SU-R01-000123",
  "run_id": "p1-2026-10-10T00:00Z",
  "process": ["shallow_debris", "deep_seated"],
  "scores": {"susceptibility": 0.71, "hazard": 0.78, "exposure": 0.64,
             "vulnerability": 0.8, "risk": 0.40, "risk_interval": [0.31, 0.52]},
  "deformation": {"status": "OK", "coverage_pct": 62, "v_downslope_mm_yr": -38.4,
                  "v_sigma_mm_yr": 4.1, "ada": true},
  "data_status": "OK",
  "unknown_reasons": [],
  "runout": {"inherited_from": ["SU-R01-000119"], "footprint_id": "RO-8812"},
  "lane": "INSTRUMENT",
  "priority_rank": 4
}
```

**TelemetryMessage** (field → Phase 2A, MQTT)
```json
{"ts": "2026-10-10T06:15:00Z", "site_id": "SITE-0007", "sensor_id": "GNSS-02",
 "channel": "gnss_enu", "values": {"e_mm": 1.2, "n_mm": -0.4, "u_mm": 0.9},
 "sigma": {"h_mm": 2.0, "v_mm": 4.0}, "quality": "OK", "battery_v": 12.6, "seq": 88412}
```

**BreachEvent** (Phase 2A / 1 → Phase 3)
```json
{"event_id": "7c1e0b5a-0000-0000-0000-000000000000", "site_id": "SITE-0007",
 "created_at": "2026-10-10T06:20:00Z", "proposed_level": "WARNING",
 "triggers": [{"rule": "v_warn", "sensor_id": "GNSS-02", "value": 12.4,
               "unit": "mm/day", "threshold_version": "th-2026-09-01"}],
 "ivm": {"status": "VALID", "tf_window_utc": ["...", "..."], "validity": "MEDIUM"},
 "rain_context": {"id_class": "EXCEEDED", "api_mm": 212},
 "monitoring_status": "NOMINAL", "evidence_url": "https://.../SITE-0007"}
```

**DroneProduct** (Phase 2B → 1 / 2A / 3): a STAC Item
```json
{"type": "Feature", "stac_version": "1.0.0", "id": "SITE-0007_2026-10-02_lidar",
 "properties": {"datetime": "2026-10-02T05:40:00Z", "mission_type": "PERIODIC",
                "ground_density_ppm2": 14.2, "reg_rmse_m": 0.03,
                "lod95_m": 0.08, "qc_status": "PASS"},
 "assets": {"dtm": "dtm_cog.tif", "pointcloud": "cloud.copc.laz",
            "change": "change_cog.tif", "scarps": "scarps.gpkg"}}
```

Phase 3 alert objects map to CAP v1.2 (see Phase 3 §7).

## 6. Build order and milestones

Durations depend on team size and data availability, so they are not given. The earlier "Phase 2 in one quarter" plan was unrealistic; plan around a **full wet season** of shadow operation.

| M | Name | Contents | Exit criteria |
|---|---|---|---|
| **M0** | Foundations | Decisions D1, D2, D6, D9; data audit and licences; inventory assembly; repo, CI, environments; permit scoping | Data catalogue complete; inventory completeness map; decision log signed |
| **M1** | Phase 1 static + retrospective | Slope units, static features, exposure, susceptibility, runout, spatial CV, calibration | Recall target (D3) met on held-out spatial blocks; reliability acceptable; D10 recorded |
| **M2** | Phase 1 dynamic | Rain fusion and I–D calibration; InSAR chain; optical layers; `UNKNOWN` logic; queue; audit sampling | Backtest on past events done; invariant tests green; freshness SLIs live |
| **M3** | Phase 3 skeleton (build early) | Workflow, expert UI, CAP builder (Exercise mode only), RBAC, audit, on-call | Tabletop + synthetic breach → CAP `Test` to an internal sink; D4, D5 decided |
| **M4** | Phase 2A pilot | 1–2 instrumented slopes; baseline noise floor; thresholds calibrated; IVM backtest; health monitoring | Uptime ≥ target; noise floor documented; expert reviews backtest |
| **M5** | Phase 2B | Baseline missions; processing; LoD from repeat flights; products flow to Phases 1 and 3 | Stable-terrain repeatability meets LoD target; QC gates automated |
| **M6** | Integrated shadow operation | All phases live; alerts to experts only; ≥ 1 wet season | Precision / recall / lead-time review; fixes shipped; no open Sev-1 |
| **M7** | Limited live pilot | Authority-approved; drills completed | Go / no-go by authority and expert |

## 7. Repository layout

```
landslide-ewp/
├── README.md                          # this file
├── contracts/                         # JSON Schema, OpenAPI, STAC extensions
├── platform/                          # IaC, k8s manifests, observability, CI
├── phase1-macro-risk-screening/README.md
├── phase2a-in-situ-monitoring/README.md
├── phase2b-drone-inspection/README.md
└── phase3-governance-alerting/README.md
```
Copy each `README-phaseX-*.md` file into its directory as `README.md`.

## 8. Cross-cutting platform requirements

| Area | Requirement |
|---|---|
| Deployment | Containers; **two planes**: alerting plane (small, multi-AZ, minimal dependencies) and analytics plane (elastic, batch). IaC (Terraform) + GitOps |
| Messaging | MQTT broker (clustered) + lightweight workers for telemetry. Kafka only if sensor count/throughput demands it |
| Batch orchestration | Apache Airflow (or Prefect) for Phase 1 and 2B pipelines |
| Storage | S3/MinIO for COG, COPC, STAC assets; PostGIS for vectors/metadata; TimescaleDB for time series; backups with point-in-time recovery |
| Observability | Prometheus + Grafana + Loki (or equivalents). SLIs: data freshness (rain, Sentinel-1, telemetry), pipeline success, queue age, review latency. Staleness alerts go to ops, never the public |
| Security | OIDC SSO + MFA, RBAC, secrets in KMS/Vault, TLS everywhere, per-device certificates, signed images, pen test before pilot |
| Data governance | STAC catalogue; run IDs and lineage; MLflow model registry; dataset versioning (DVC/lakeFS); licence register (DEM, imagery, buildings); privacy impact assessment |
| Quality | CI with unit + contract tests; replay/backtest suites; quarterly game days; release gates tied to milestones |
| Resilience | RPO/RTO defined for the alerting plane; out-of-band notification path (≥ 2 SMS/voice providers) |

## 9. Open decisions

| ID | Decision | Owner | Needed by |
|---|---|---|---|
| D1 | Failure types in scope (shallow/debris, rockfall, deep-seated, debris-flow channels) | Product + expert | M0 |
| D2 | Pilot region; inventory source and completeness | Product + geo team | M0 |
| D3 | Recall target R and flagged-area budget | Expert + authority | M1 |
| D4 | Alert SLAs: expert (source: 15 min), authority, total capture-to-broadcast; false-alarm budget | Authority + expert | M3 |
| D5 | Pre-authorised automatic local actions for rapid-onset hazards (yes/no, where) | Authority | M3 |
| D6 | DEM choice and licensing (check non-commercial restrictions) | Geo team | M0 |
| D7 | Number of Tier A instrumented sites and budget | Programme | M4 |
| D8 | Drone operations model (in-house vs contractor); BVLOS / night permissions | Ops + regulator | M5 |
| D9 | Hosting and data residency | Platform | M0 |
| D10 | Named sign-off authority for thresholds and the change-control process | Authority | M1 |

## 10. Glossary

- **ADA** — Active Deformation Area: spatial cluster of coherent InSAR pixels with significant motion
- **API** — Antecedent Precipitation Index
- **CAP** — Common Alerting Protocol (OASIS), v1.2
- **I–D threshold** — Rainfall intensity–duration curve above which landslides become likely
- **IVM** — Inverse-velocity method (Fukuzono): extrapolates 1/v → 0 to estimate time of failure
- **LoD95** — Level of detection at 95 % confidence: smallest change distinguishable from noise
- **Slope unit** — Terrain unit bounded by drainage and ridge lines (half-basin)
- **TARP** — Trigger-Action-Response Plan: quantified triggers mapped to defined actions
- **TTF** — Time to failure
