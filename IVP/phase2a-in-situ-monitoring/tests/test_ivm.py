"""Test Inverse-Velocity Module (IVM) tertiary creep forecasting and guardrails."""

import numpy as np
import pytest
from datetime import datetime, timezone
from ewp_p2a.engine.ivm import IVMEngine
from ewp_p2a.common.types import IVMStatus


def test_ivm_accelerating_tertiary_creep_forecast():
    """Verify Fukuzono/Voight tertiary creep forecasting on accelerating velocity series."""
    engine = IVMEngine(n_min=5, v_min_threshold_mm_day=2.0)
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

    # Accelerating velocity sequence: 4 -> 8 -> 15 -> 28 -> 55 mm/day
    t_days = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    v_series = np.array([5.0, 8.0, 14.0, 26.0, 50.0])
    v_sigmas = np.array([0.5, 0.6, 0.8, 1.2, 2.0])

    forecast = engine.run_ivm_forecast(
        time_days=t_days,
        velocities_mm_day=v_series,
        v_sigmas=v_sigmas,
        rain_pulse_active=False,
        current_time=now,
    )

    assert forecast.status == IVMStatus.VALID
    assert forecast.tf_window_utc is not None
    assert len(forecast.tf_window_utc) == 2
    assert forecast.validity in ["LOW", "MEDIUM", "HIGH"]


def test_ivm_rain_pulse_guardrail():
    """Verify Section 7.2 guardrail: acceleration coinciding with rain pulse is flagged RAIN_PULSE, not Critical."""
    engine = IVMEngine(n_min=5)
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

    t_days = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    v_series = np.array([5.0, 8.0, 14.0, 26.0, 50.0])
    v_sigmas = np.array([0.5, 0.5, 0.5, 0.5, 0.5])

    # Rain pulse active
    forecast = engine.run_ivm_forecast(
        time_days=t_days,
        velocities_mm_day=v_series,
        v_sigmas=v_sigmas,
        rain_pulse_active=True,
        current_time=now,
    )

    assert forecast.status == IVMStatus.RAIN_PULSE
    assert "RAIN_PULSE_CORRELATED" in forecast.flags


def test_ivm_below_noise_floor_suppression():
    """Low velocities near noise floor must be suppressed (BELOW_NOISE_FLOOR)."""
    engine = IVMEngine(v_min_threshold_mm_day=3.0)
    t_days = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    # Very low creeping velocities (0.2 - 0.5 mm/day)
    v_series = np.array([0.2, 0.3, 0.3, 0.4, 0.5])
    v_sigmas = np.array([0.4, 0.4, 0.4, 0.4, 0.4])

    forecast = engine.run_ivm_forecast(
        time_days=t_days,
        velocities_mm_day=v_series,
        v_sigmas=v_sigmas,
        rain_pulse_active=False,
    )

    assert forecast.status == IVMStatus.BELOW_NOISE_FLOOR
