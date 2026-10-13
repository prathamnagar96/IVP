# Phase 2B — Targeted Drone Inspection & 3D Change Detection

This implementation follows the Phase 2B build specification in the repository
root. It provides deterministic, dependency-light building blocks for mission
planning, weather/permit go-no-go checks, repeat-flight change detection,
quality gates, and STAC `DroneProduct` construction. Heavy LiDAR/SfM tools
(PDAL, ODM, py4dgeo) remain pipeline adapters and are intentionally not hidden
behind fake implementations.

## Quick start

```powershell
python -m pytest
```

The package is importable from `src` and has no cloud or GIS runtime
dependency. Arrays passed to change detection must already be co-registered
and use the same cell grid.

## Safety boundary

`FAIL` QC blocks product release. A grounded mission remains queued; the
planner never silently authorizes a flight when weather, permits, or crew
requirements are not satisfied.

## Layout

```text
phase2b-drone-inspection/
├── config/default.yaml
├── docs/field-protocol.md
├── planner/mission.py
├── src/ewp_p2b/
│   ├── change/dod.py
│   ├── qc/gates.py
│   └── stac/item.py
└── tests/
```
