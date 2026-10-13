# Phase 3 — Governance, Human Validation & Alerting

This package implements the safety-critical alerting-plane primitives described
in the repository Phase 3 specification:

- explicit event state transitions and SLA escalation;
- mandatory expert and authority approvals for public broadcasts;
- CAP v1.2 XML generation for exercise/test/live modes;
- stepwise de-escalation and all-clear checks;
- append-only hash-chained audit records; and
- channel delivery receipts and basic KPI calculations.

The default is `Exercise` mode. `Actual` output must be explicitly selected by
the caller after authority approval. Local actuation is not implemented as a
public-alert bypass and remains disabled by default.

```powershell
python -m pytest
```

## Technical image-processing console

`ui/dashboard.html` is a browser-openable technical demonstrator for the
imagery hand-off into Phases 1 and 2B. It is deliberately not an alerting
dashboard and it does not claim to produce calibrated risk results.

Open the file directly in a browser, then choose one of these input paths:

1. **STAC search (recommended for a demonstration):** enter an AOI as
   `west,south,east,north` in WGS84, a date range, and cloud threshold. The
   default public Earth Search endpoint returns Sentinel-2 scene metadata and
   preview assets.
2. **Local image:** choose a PNG or JPEG to exercise the browser preview and
   pixel-statistics hand-off. This is only a smoke test; ordinary images have
   no CRS, calibrated bands, or satellite metadata.
3. **Real processing input:** stage georeferenced GeoTIFF/COG bands, a DEM,
   AOI/slope-unit GeoJSON, and the required rainfall/exposure layers for the
   Phase 1 Python pipeline. Sentinel-1 InSAR additionally requires a
   compatible multi-acquisition SAR stack, orbit files, coherence and
   atmospheric processing. A single JPEG cannot produce deformation velocity.

The page labels its browser-only output as `DEGRADED` and creates a
`DRONE_BASELINE` candidate rather than silently presenting a public warning.
The production path still needs authenticated downloads or a scheduled STAC
worker, raster processing adapters, immutable raw-data storage, and validation
against the shared QueueItem contract before any result is eligible for Phase 3
governance.
