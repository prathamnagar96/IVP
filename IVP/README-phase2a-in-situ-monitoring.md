# Phase 2A — Continuous In-Situ Monitoring & Early-Warning Engine

> Part of the [Landslide EWP build guide](README.md). Safety-critical: every threshold below is a placeholder for site calibration and expert sign-off.

## At a glance

| | |
|---|---|
| **Goal** | Measure ground movement, pore pressure and rainfall continuously on critical slopes, and turn those measurements into quantified, expert-reviewable warning triggers |
| **Scope** | Instrumented slopes only (Tier A and B sites chosen from the Phase 1 `INSTRUMENT` lane) |
| **Inputs** | Field sensors; Phase 1 queue items and rain context; Phase 2B baseline products |
| **Outputs** | Clean time series, velocity/acceleration, `BreachEvent` messages, sensor-health status |
| **Cadence** | Seconds to minutes (telemetry); rules evaluated every few minutes |
| **Consumed by** | Phase 3 (alerting), Phase 2B (verification missions), Phase 1 (backtest library) |
| **Depends on** | M3 (Phase 3 skeleton) so events have somewhere to go; decisions D1, D5, D7, D10 |

## 1. Purpose, scope, non-goals

- Provide the **only** time-to-failure logic in the platform. Drones and satellites cannot resolve millimetre-per-day creep at hourly cadence; ground sensors can.
- Support three triggering paths: **kinematic** (velocity/acceleration), **hydrological** (rain, soil moisture, pore pressure) and **rapid-onset** (§7.3).
- Never present a single time-to-failure number as truth. Output windows with validity flags, for expert use only.

**Non-goals:** regional screening (Phase 1), cm-scale mapping (Phase 2B), public alerting (Phase 3).

## 2. Interfaces

| Direction | Data | Contract |
|---|---|---|
| In | `TelemetryMessage` from field loggers (MQTT) | root README §5 |
| In | Queue items, regional rain context | Phase 1 |
| In | Baseline DTM and joint-set data | Phase 2B |
| Out | `BreachEvent` (proposed level, triggers, IVM window, rain context, health) | root README §5 |
| Out | Site health and ops notifications | Phase 3 (ops channel) |
| Out | Confirmed-event time series | Backtest library |

## 3. Architecture

```
 Sensors (GNSS · piezometer · inclinometer · extensometer · tilt · rain · soil moisture · geophone)
        │ data loggers (local buffer ≥ N days)
        ▼
 Gateway → cellular (+ satellite / radio backup) → MQTT broker (TLS, QoS 1)
        ▼
 Ingestion workers: validate → dedupe → raw (immutable) → QC → TimescaleDB (+ aggregates)
        ▼
 Processing: GNSS solutions · compensation · noise floor · velocity / acceleration
        ▼
 ┌──────────────────── Early-warning engine ──────────────────┐
 │ TARP rules ── IVM windows ── rapid-onset triggers ──────────┼─► BreachEvent ─► Phase 3
 │ Sensor-health monitor (NOMINAL / DEGRADED / BLIND) ─────────┘
 └──────────────────────────────────────────────────────────────┘
       ▲ versioned site thresholds                ▲ Phase 1 rain context
```

## 4. Site selection and instrumentation design

### 4.1 Workflow
Queue `INSTRUMENT` lane → desk study (geology, history, imagery, Phase 2B DTM) → field reconnaissance and geotechnical assessment → **mechanism classification** → instrumentation design → agreements (landowner, authority) → installation → baseline period → threshold calibration → go-live.

**Tiers**
- **Tier A (full suite):** high exposure and (active deformation or very high susceptibility)
- **Tier B (light):** rain gauge + tilt/crack/soil-moisture sensing + telemetry
- **Tier C:** satellite-only (Phase 1) + periodic drone

The number of Tier A sites is capped by budget (D7). Each has a named owner and an O&M plan.

### 4.2 Mechanism → sensors

| Mechanism | Core sensors | Optional | Notes |
|---|---|---|---|
| Deep-seated slide | Multi-antenna GNSS (≥ 2 on the moving mass + 1 stable reference), in-place inclinometers or shape arrays, vibrating-wire piezometers at/above shear zone, wire extensometers across scarps, rain gauge | Tiltmeters, ground-based radar | Needs boreholes and geotechnical investigation; inclinometers give shear-zone depth |
| Shallow rain-induced slide | Rain gauges, volumetric water content + tensiometers at 2–3 depths, tiltmeters / crackmeters | Piezometers, cameras | Mostly hydrological triggers; rapid onset (§7.3) |
| Rock slope / rockfall | Crackmeters / extensometers across open joints, tiltmeters, temperature, rain gauge | Geophones / acoustic emission, time-lapse cameras, ground-based radar | Phase 2B facets define joint sets |
| Debris-flow channel | Catchment rain gauges, geophones / flow radar / stage sensors, cameras | Pore pressure in source area | Minutes of lead time: §7.3 and decision D5 |

GNSS is typically millimetre-level in daily static solutions but centimetre-level for short kinematic windows. Design thresholds around the window you can actually resolve.

### 4.3 Layout rules
- Reference station on **stable ground outside** the moving mass.
- ≥ 2 independent measurements of each critical quantity (e.g. GNSS + extensometer) so one failure cannot blind the site.
- No single point of failure in power or comms.
- As-built record per sensor: type, serial, calibration, coordinates, orientation, install date.

## 5. Telemetry, power and ingestion

### 5.1 Field stack
Sensor → data logger (local buffer ≥ N days) → gateway → cellular primary + satellite/radio backup → MQTT broker. Solar + battery sized for the worst-case overcast period plus margin; surge/lightning protection; enclosure rated for site; time sync from GNSS.

### 5.2 MQTT
- Topic: `ewp/{region}/{site_id}/{sensor_id}/{channel}`; heartbeat on `.../status`.
- TLS with per-device certificates; QoS 1 (at-least-once ⇒ **duplicates happen, make writes idempotent**).
- Payload: `TelemetryMessage` (root README §5), including `seq`, `quality`, `battery_v`.

### 5.3 Ingestion workers
validate schema/range/timestamp → dedupe on `(sensor_id, channel, ts)` → write raw (immutable) → QC → QC'd table → continuous aggregates (1 h, 1 d). Late data from logger back-fill after outages is accepted; the engine recomputes affected windows.

### 5.4 Storage

```sql
CREATE TABLE sensor_readings (
  ts timestamptz NOT NULL, site_id text NOT NULL, sensor_id text NOT NULL,
  channel text NOT NULL, value double precision, sigma double precision,
  quality smallint NOT NULL DEFAULT 0, seq bigint,
  PRIMARY KEY (sensor_id, channel, ts)
);
SELECT create_hypertable('sensor_readings', 'ts');
-- add compression policy after N days; retention on raw per data policy
```
Other tables: `sites`, `sensors` (metadata), `sensor_health`, `noise_floor`, `thresholds` (versioned), `ivm_results`, `breach_events`.

## 6. Signal processing and measurement QC

1. **GNSS:** relative positioning against the stable base (RTKLIB or vendor engine). Daily static solutions for mm-level trends; short-window kinematic solutions for fast events. Reject by solution quality (fixed vs float, ratio test). Output local ENU.
2. **Compensation:** temperature for extensometers and tiltmeters; barometric for non-vented piezometers; per manufacturer. Remove diurnal thermal cycles by harmonic fit.
3. **Noise floor:** from a baseline period (≥ N weeks) per sensor and channel; store σ in `noise_floor`; re-estimate quarterly.
4. **Direction:** project vectors onto the movement direction (from inclinometer / GNSS vector orientation) → `d_along` scalar.
5. **Velocity:** robust (Theil–Sen) slope in a moving window `W` sized so expected displacement over `W` ≥ `SNR_min × σ`. Use several scales (1 h, 6 h, 24 h, 7 d). Output `v`, `σ_v`; acceleration from successive velocities. Hampel filter for spikes. **Do not interpolate across long gaps.**

## 7. Early-warning engine

### 7.1 TARP (trigger-action-response plan)
Thresholds are **site-calibrated, versioned configuration**, never code constants. Triggers are expressed relative to the measured noise floor and require persistence and corroboration.

```yaml
site: SITE-0001
mechanism: deep_seated
threshold_version: th-YYYY-MM-DD       # change-controlled (Phase 3 §4.4)
sensors:
  primary: [GNSS-01, GNSS-02, EXT-01]
  corroborating: [PZ-01, TILT-01]
noise_floor: {gnss_h_mm: null, ext_mm: null, v_mm_day: null}   # from baseline
levels:
  advisory:
    any_of:
      - {v_downslope_mm_day: ">= k_adv * noise_v", persist_h: null}
      - {rain_id_class: ">= EXCEEDED"}
  warning:
    all_of:
      - {v_downslope_mm_day: ">= v_warn", corroborated_by: ">= 2 sensors"}
    any_of:
      - {accel_flag: true}
      - {piezo_head_m: ">= pz_warn"}
  critical:
    any_of:
      - {ivm: {status: VALID, tf_window_h: "<= tf_crit_h"}}
      - {v_downslope_mm_day: ">= v_crit"}
      - {piezo_head_m: ">= pz_crit"}
    requires: expert_review
de_escalation: {all_below: advisory, for_h: T_clear_h, rain_exceedance: false, verification: drone_or_field}
```

- **Corroboration:** k-of-n voting across independent sensors; documented exceptions for designated primary sensors that pass QC.
- **Persistence:** a trigger must hold for `persist_h` to avoid single-spike alarms.
- Initial values come from expert judgement and are tightened only after baseline data and backtests.

### 7.2 Inverse-velocity module (IVM)
Empirical (Fukuzono / Voight), **not** physics-based. Valid only during accelerating (tertiary) creep.

```python
def ivm_forecast(t, d, cfg):
    v, v_sigma = robust_velocity(t, d, window=cfg.vel_window)      # mm/day, smoothed
    if not accelerating(v, cfg):          # sustained dv/dt > 0, Mann-Kendall p < 0.05, v > snr_min * v_sigma
        return Forecast(status="NOT_ACCELERATING")
    y = v ** (1 - cfg.alpha)              # alpha = 2  ->  1/v ; generalised form v^(1-alpha)
    fit = theil_sen(t[-cfg.n:], y[-cfg.n:])      # n >= cfg.n_min
    if fit.slope >= 0:
        return Forecast(status="NO_CONVERGENCE")
    tf = -fit.intercept / fit.slope       # time at which y -> 0
    lo, hi = bootstrap_percentiles(t, y, cfg, q=(5, 95))
    return Forecast(status="VALID", tf=tf, window=(lo, hi),
                    validity=grade(fit, rain_flag(t, cfg)), flags=flags(t, cfg))
```

**Guardrails**
- Do not run below `v_min` / noise (1/v is noise-dominated at low velocity).
- Require ≥ `n_min` points on the accelerating trend and a significant monotone decrease of `1/v`.
- Flag `RAIN_PULSE` when acceleration coincides with rainfall (1/v can reverse once rain stops).
- Report a window and a validity grade (`LOW`/`MEDIUM`/`HIGH`), plus how stable `tf` has been over the last N refits.
- IVM output is an **input** to a Critical *proposal*, never a stand-alone alarm, and never published to the public.
- Not applicable to sudden or rain-triggered failures without accelerating creep.

### 7.3 Rapid-onset path (shallow slides, debris flows)
- Triggers are hydrological or physical: rainfall above locally calibrated I–D curves, soil moisture / pore-pressure thresholds, geophone or flow-radar triggers in channels.
- No IVM. Lead time may be minutes, so the Phase 3 **fast lane** is used (expert paged immediately; pre-staged evidence).
- Optional pre-authorised **local** actuation (road gate, local siren, signal) only via decision D5: physical-sensor triggers, not ML outputs, signed off by the authority, tested in Exercise mode, with a kill switch.

### 7.4 Evidence pack
Each `BreachEvent` bundles: the triggering series with noise-floor bands, velocity/acceleration plots, IVM window and validity, rainfall vs thresholds, piezometer trends, sensor health, latest drone change map, and Phase 1 risk/runout/exposure.

### 7.5 Outputs
`BreachEvent` is idempotent (same `event_id` while the episode lasts), re-emitted on level change, and delivered by webhook/queue with retry and dead-letter handling.

## 8. Sensor health and "blind" handling

Per-sensor state from heartbeat, stale data, flatline, spike rate, battery and signal strength: `HEALTHY` / `DEGRADED` / `FAILED`.

| Site status | Meaning | Action |
|---|---|---|
| `NOMINAL` | All primary measurements healthy | normal |
| `DEGRADED` | Some sensors lost, redundancy remains | ticket; inspection SLA |
| `BLIND` | A primary measurement is lost | **Immediate ops notification to Phase 3; conservative posture** (treat as elevated; request drone/field check; shorter review cadence) |

**A blind site is never treated as stable.** Dashboards show last-known values with their age.

## 9. Operations and maintenance

| Task | Frequency (placeholder) |
|---|---|
| Remote health review | Daily automated, weekly human |
| Site visit: cleaning, vegetation, connections, battery | Quarterly |
| Sensor calibration / replacement | Per manufacturer; annually minimum |
| Noise-floor and threshold review | Quarterly and after any significant event |
| Spares inventory and lightning/surge checks | Annually and after storm season |

Safety: **no personnel on or below the moving mass** during Warning/Critical; lone-worker procedures; site-access permits; vandalism and wildlife protection. Budget O&M explicitly; an unmaintained site becomes a `BLIND` site.

## 10. Configuration

Site config = YAML in §7.1 + a `site.yaml` (sensor list, geometry, mechanism, contacts). Thresholds live in a versioned store with the change control defined in Phase 3 §4.4.

## 11. Repository layout

```
phase2a-in-situ-monitoring/
├── README.md
├── field/              # logger firmware configs, installation checklists, templates
├── config/sites/       # site.yaml, tarp.yaml per site
├── src/ewp_p2a/
│   ├── ingest/         # MQTT consumer, validation, dedupe
│   ├── processing/     # GNSS, compensation, noise floor, velocity
│   ├── engine/         # tarp, ivm, rapid_onset, corroboration
│   ├── health/         # sensor and site status
│   └── publish/        # BreachEvent emitter
├── sql/                # DDL, hypertables, aggregates
├── tests/              # unit, replay, chaos
└── backtest/           # replay datasets, scenarios, reports
```

## 12. Testing and backtesting

**Bench / unit:** schema validation, idempotent ingest, duplicate and out-of-order messages, unit conversions, projection onto movement direction.

**Replay and synthetic scenarios** (replayed through the real MQTT path):
- Accelerating creep with noise for several exponents α; with and without gaps
- Rain pulses that cause temporary acceleration then recovery (must be flagged `RAIN_PULSE`, not Critical)
- Spikes, drift, flatline, battery sag, comms outage; late-arriving back-fill
- Historical failure series (published case studies, geological-survey or partner archives)

**Metrics:** lead-time distribution, false alarms per site-year, missed events, time from data to proposal, fraction of time `NOMINAL`.

**Chaos tests:** broker down, DB lag, worker crash, clock skew. The engine must degrade to `BLIND`/`DEGRADED` and notify, never fail silently.

## 13. Acceptance criteria

- [ ] Baseline period complete; noise floor documented per sensor
- [ ] Thresholds calibrated and signed off by the engineering geologist (D10); version recorded
- [ ] Backtests reviewed by an expert: lead time and false-alarm metrics within agreed bounds
- [ ] Telemetry uptime ≥ target; `BLIND` detection verified by fault injection
- [ ] End-to-end: synthetic breach → `BreachEvent` → Phase 3 within latency budget (D4)
- [ ] O&M plan, spares and named site owner in place
- [ ] Rapid-onset path tested (and D5 decided)

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Single-sensor glitch triggers an alarm | Persistence + corroboration + QC |
| IVM misused as a precise clock | Windows, validity grades, expert-only, guardrails |
| Rain-pulsed creep misread as failure trend | `RAIN_PULSE` flag; rain context in evidence pack |
| Power/comms loss during storms | Redundant comms, buffers, solar sizing, `BLIND` escalation |
| Sensor drift and ageing | Calibration schedule, drift monitoring |
| Thresholds set too tight/loose | Baseline first; conservative start; quarterly review |
| Cost of instrumenting many slopes | Tiering, cap on Tier A (D7), satellite-only Tier C |

## 15. Open decisions (Phase 2A)

- D1 failure types; D5 pre-authorised local actuation; D7 Tier A count and budget; D10 threshold sign-off
- Telemetry carrier and backup (cellular vs satellite vs radio) per region
- Who performs site installation, maintenance and emergency access
