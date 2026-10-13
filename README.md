# Automated Terrain Stability Monitoring & Early Warning Platform (EWP)

An enterprise-grade, 4-phase integrated geospatial platform for landslide susceptibility screening, real-time in-situ telemetry monitoring, targeted 3D drone inspection, and human-gated governance alerting.

---

## 📊 Presentation Deck & Defense Materials

This repository contains all presentation resources and quantitative metrics required for final project evaluation:

- **Interactive Presentation Deck:** [`presentation.html`](./presentation.html) (Stand-alone HTML presentation deck)
- **Technical Console / WebGIS Dashboard:** [`phase3-governance-alerting/ui/dashboard.html`](./phase3-governance-alerting/ui/dashboard.html)
- **Verification Suite:** 51 passing automated test cases across all 4 operational phases.

---

## ⚙️ System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          EWP OPERATIONAL ARCHITECTURE                            │
└──────────────────────────────────────────────────────────────────────────────────┘
   │
   ├── Phase 1: Macro-Risk Screening Engine (`ewp_p1`)
   │    ├── Horn (1981) 3x3 finite-difference slope & curvature calculation
   │    ├── 10 km spatial block cross-validation (0 data leakage)
   │    ├── Sentinel-1 InSAR downslope velocity projection
   │    └── Priority queue assignment (`INSTRUMENT`, `DRONE_BASELINE`, `RESCREEN`)
   │
   ├── Phase 2A: Continuous In-Situ Telemetry Engine (`ewp_p2a`)
   │    ├── MQTT streaming to TimescaleDB hypertables
   │    ├── Dynamic noise floor & barometric compensation
   │    ├── Fukuzono tertiary creep extrapolation ($1/v \to 0$)
   │    └── `RAIN_PULSE` transient storm-induced acceleration filter
   │
   ├── Phase 2B: Targeted Drone Inspection Engine (`ewp_p2b`)
   │    ├── Go/No-Go flight safety scheduler (wind, visibility, battery)
   │    ├── Stable-bedrock ICP point cloud co-registration
   │    └── M3C2 3D change detection ($\text{LoD}_{95} = 1.96 \sqrt{\sigma_1^2 + \sigma_2^2}$)
   │
   └── Phase 3: Governance, CAP v1.2 & Audit Ledger (`ewp_p3`)
        ├── Two-Person RBAC Identity Rule (Duty Expert + Civil Authority)
        ├── OASIS Common Alerting Protocol v1.2 XML payload generator
        └── Tamper-evident SHA-256 hash-chained audit log
```

---

## 🚀 Live Demonstration Steps (For Presentation on Any Computer)

You do **not** need a local Python environment or backend server installed on the college presentation computer. Follow these steps to perform a live demonstration:

### Option A: WebGIS Dashboard & STAC Demonstration (Browser Only)
1. Clone or download this repository on the presentation PC:
   ```bash
   git clone https://github.com/prathamnagar96/IVP.git
   cd IVP
   ```
2. Open `phase3-governance-alerting/ui/dashboard.html` directly in any modern browser (Chrome, Edge, Firefox).
3. **Live Satellite Discovery:**
   - Click **`Search STAC`** on the left sidebar to query live Sentinel-2 satellite passes from AWS Earth Search.
   - Click **`Preview`** on any returned scene.
   - Click **`Run local preview analysis`** to trigger real-time candidate segmentation, terrain stability overlays (`CRITICAL`, `MODERATE`, `STABLE`), and risk JSON payload generation.
4. **Local Raster Inspection:**
   - Click **`Choose File`** and upload any local terrain/slope image.
   - Click **`Run local preview analysis`** to display interactive pixel metrics and output JSON candidate hand-offs.

---

### Option B: Running Full Verification Tests (If Python is Available)
If Python 3.10+ is installed on the presentation PC, run the entire platform test suite to demonstrate backend rigor:

```bash
# Clone and enter repo
git clone https://github.com/prathamnagar96/IVP.git
cd IVP

# Install pytest
pip install pytest

# Execute all test suites across all 4 phases
pytest phase1-macro-risk-screening/tests -q
pytest phase2a-in-situ-monitoring/tests -q
pytest phase2b-drone-inspection/tests -q
pytest phase3-governance-alerting/tests -q
```
**Expected Output:** `51 passed in <1.5s`

---

## 📈 Quantitative Performance & Benchmarks

| Metric / Test Case | Result | Specification / Benchmark |
| :--- | :--- | :--- |
| **Horn Slope Synthetic Benchmark** | $30.0000^\circ$ | $\pm 0.0001^\circ$ exact numerical accuracy |
| **Spatial Cross-Validation** | 10 km Spatial Blocks | Zero spatial autocorrelation leakage |
| **Drone LiDAR M3C2 Detection** | $\text{LoD}_{95}$ | $1.96 \sqrt{\sigma_1^2 + \sigma_2^2}$ |
| **Tertiary Creep Filter** | Fukuzono $1/v \to 0$ | Storm-induced speedup filtering via `RAIN_PULSE` |
| **Alert Governance Rule** | Enforced | Strict 2-person identity separation for CAP v1.2 |
| **System Test Coverage** | **51 Passed** | 0 Failures / 0 Errors across all phases |

---

## 📄 License
This project is part of a final-year engineering defense and is released under the MIT License.
