"""Test TARP rules, corroboration (k-of-n voting), persistence, and rapid onset."""

import pytest
from datetime import datetime, timedelta, timezone
from ewp_p2a.engine.tarp import TARPEngine
from ewp_p2a.engine.corroboration import CorroborationEngine
from ewp_p2a.engine.rapid_onset import RapidOnsetEngine
from ewp_p2a.common.types import (
    ProposedLevel,
    IVMForecast,
    IVMStatus,
)


def test_tarp_warning_requires_corroboration():
    """Verify Section 7.1 rule: Warning requires v >= v_warn corroborated by >= 2 independent sensors."""
    tarp_cfg = {
        "threshold_version": "th-2026-09-01",
        "levels": {
            "advisory": {"v_downslope_mm_day": 4.5},
            "warning": {
                "v_downslope_mm_day": 10.0,
                "corroboration_min_sensors": 2,
                "piezo_head_increase_m": 5.0,
            },
            "critical": {"v_downslope_mm_day": 50.0},
        },
    }
    engine = TARPEngine(tarp_cfg)
    ivm_idle = IVMForecast(status=IVMStatus.NOT_ACCELERATING)

    # 1. Single sensor exceeding 10 mm/day without second corroborating sensor -> Cannot be Warning!
    res_single = engine.evaluate_site_tarp(
        sensor_velocities={"GNSS-02": 14.5},
        sensor_accelerations={"GNSS-02": 1.2},
        piezo_head_increase_m=0.0,
        ivm_forecast=ivm_idle,
        rain_id_class="NORMAL",
    )
    # Stays at Advisory because second sensor corroboration is missing
    assert res_single["proposed_level"] == ProposedLevel.ADVISORY

    # 2. Dual sensors both exceeding 10 mm/day (GNSS-02 and EXT-01) -> Promoted to Warning!
    res_corroborated = engine.evaluate_site_tarp(
        sensor_velocities={"GNSS-02": 14.5, "EXT-01": 12.0},
        sensor_accelerations={"GNSS-02": 1.2, "EXT-01": 0.8},
        piezo_head_increase_m=0.0,
        ivm_forecast=ivm_idle,
        rain_id_class="NORMAL",
    )
    assert res_corroborated["proposed_level"] == ProposedLevel.WARNING
    assert len(res_corroborated["triggers"]) >= 2


def test_tarp_critical_on_valid_ivm():
    """Verify Section 7.1 rule: Valid IVM tertiary forecast triggers Critical level."""
    tarp_cfg = {
        "threshold_version": "th-2026-09-01",
        "levels": {
            "advisory": {"v_downslope_mm_day": 4.5},
            "warning": {"v_downslope_mm_day": 10.0, "corroboration_min_sensors": 2},
            "critical": {"v_downslope_mm_day": 50.0},
        },
    }
    engine = TARPEngine(tarp_cfg)

    valid_ivm = IVMForecast(
        status=IVMStatus.VALID,
        tf_window_utc=["2026-10-11T12:00:00Z", "2026-10-12T00:00:00Z"],
        validity="HIGH",
    )

    res = engine.evaluate_site_tarp(
        sensor_velocities={"GNSS-02": 15.0},
        sensor_accelerations={"GNSS-02": 2.0},
        piezo_head_increase_m=0.0,
        ivm_forecast=valid_ivm,
        rain_id_class="NORMAL",
    )

    assert res["proposed_level"] == ProposedLevel.CRITICAL
    assert any(t.rule == "ivm_imminent_failure_window" for t in res["triggers"])


def test_rapid_onset_fast_lane():
    """Verify Section 7.3 rapid-onset triggers for debris flow geophones and sudden pore pressure spikes."""
    rapid = RapidOnsetEngine()

    # Sudden acoustic signal on channel geophone
    res = rapid.evaluate_rapid_onset(
        rain_id_class="EXCEEDED",
        geophone_max_mv=320.0,  # > 250 mV threshold
    )

    assert res["triggered"] is True
    assert res["proposed_level"] == ProposedLevel.CRITICAL.value
    assert res["fast_lane"] is True
