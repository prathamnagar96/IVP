"""End-to-end pipeline screening test and retrospective historical validation (Section 9, 10)."""

from datetime import datetime, timezone
import pytest
from ewp_p1.pipeline import Phase1Pipeline
from ewp_p1.common.types import Lane, DataStatus


def generate_synthetic_regional_units(count: int = 50):
    """Generate realistic regional dataset of slope units with diverse risk profiles."""
    units = []
    for i in range(count):
        uid = f"SU-R01-{i:06d}"

        # Unit 0 is a known historical active failure slope (high S, ADA active, high exposure)
        if i == 0:
            s = 0.85
            ada = True
            v_down = -45.0
            pop = 800.0
            bldg = 150
            status = "OK"
        # Unit 1 is an unobserved dense forest slope with high exposure (UNKNOWN deformation)
        elif i == 1:
            s = 0.72
            ada = False
            v_down = 0.0
            pop = 400.0
            bldg = 60
            status = "UNKNOWN"
        # Unit 2 is a moderate slope with ADA detected
        elif i == 2:
            s = 0.55
            ada = True
            v_down = -28.0
            pop = 100.0
            bldg = 20
            status = "OK"
        # Other units
        else:
            s = 0.15 + (i % 7) * 0.08
            ada = False
            v_down = -2.0
            pop = 5.0
            bldg = 1
            status = "OK" if i % 5 != 0 else "DEGRADED"

        qualities = {
            "deformation": {"status": status, "reason": "coherence drop" if status == "UNKNOWN" else ""},
            "optical": {"status": "OK", "reason": ""},
            "rainfall": {"status": "OK", "reason": ""},
            "structure": {"status": "OK", "reason": ""},
        }

        units.append({
            "unit_id": uid,
            "susceptibility": s,
            "centroid_3d": (float(i * 200), float(i * 100), 1200.0 - float(i * 10)),
            "downhill_neighbors": [f"SU-R01-{i+1:06d}"] if i < count - 1 else [],
            "internal_exposure_elements": {
                "population": pop,
                "buildings": bldg,
                "critical_facilities": 1 if i == 0 else 0,
                "road_km": 2.5 if i < 3 else 0.5,
            },
            "deformation": {
                "status": status,
                "coverage_pct": 20.0 if status == "UNKNOWN" else 75.0,
                "v_downslope_mm_yr": v_down,
                "v_sigma_mm_yr": 3.0,
                "ada": ada,
            },
            "feature_qualities": qualities,
            "previous_lane": Lane.NONE.value,
        })
    return units


def test_end_to_end_screening_cycle_and_retrospective_flagging():
    """Verify that Phase1Pipeline runs end-to-end and satisfies retrospective would-have-flagged criterion."""
    pipeline = Phase1Pipeline()
    regional_units = generate_synthetic_regional_units(count=40)

    rain_feed = {
        "hourly_rain_mm": [2.5] * 24,
        "daily_rain_mm": [25.0] * 14,
        "duration_h": 6.0,
        "intensity_mm_h": 18.0,  # Intense storm
    }

    result = pipeline.run_screening_cycle(
        slope_units_data=regional_units,
        rainfall_feed_data=rain_feed,
        run_timestamp=datetime(2026, 10, 13, 14, 0, tzinfo=timezone.utc),
        event_trigger_active=True,  # Test acute event
    )

    # 1. Output structures check
    assert "lineage" in result
    assert "queue_items" in result
    assert "advisories" in result
    assert "summary" in result

    queue_items = result["queue_items"]
    assert len(queue_items) == 40

    # 2. Invariant I1 & I2 checks
    for item in queue_items:
        assert item.data_status in [DataStatus.OK.value, DataStatus.DEGRADED.value, DataStatus.UNKNOWN.value]
        assert item.scores.risk >= 0.0
        if item.data_status == DataStatus.UNKNOWN.value:
            # UNKNOWN => lane != NONE
            assert item.lane != Lane.NONE.value

    # 3. Retrospective 'would-have-flagged' acceptance test (Section 9, 10):
    # Historical failure unit 0 (SU-R01-000000) must be in INSTRUMENT or DRONE_BASELINE
    unit_0 = next(u for u in queue_items if u.slope_unit_id == "SU-R01-000000")
    assert unit_0.lane in [Lane.INSTRUMENT.value, Lane.DRONE_BASELINE.value]
    assert unit_0.deformation.ada is True
    assert unit_0.priority_rank is not None and unit_0.priority_rank <= 5

    # Unit 1 (unobserved terrain with high exposure) must be in RESCREEN (never NONE)
    unit_1 = next(u for u in queue_items if u.slope_unit_id == "SU-R01-000001")
    assert unit_1.data_status == DataStatus.UNKNOWN.value
    assert unit_1.lane == Lane.RESCREEN.value

    # 4. Regional Advisories candidate produced for Phase 3
    advisories = result["advisories"]
    assert len(advisories) >= 1
    adv = advisories[0]
    assert adv.region_id == "R01"
    assert adv.level in ["ADVISORY", "WARNING_CANDIDATE"]
    assert adv.rainfall_summary.api_mm > 0.0
