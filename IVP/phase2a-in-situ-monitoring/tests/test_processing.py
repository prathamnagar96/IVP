"""Test signal processing, displacement vector projection, and filtering."""

import numpy as np
import pytest
from ewp_p2a.processing.displacement import (
    project_vector_to_movement_direction,
    apply_temperature_compensation,
    apply_barometric_compensation,
)
from ewp_p2a.processing.velocity import (
    apply_hampel_filter,
    compute_theil_sen_velocity,
    compute_acceleration,
)


def test_vector_projection_onto_movement_direction():
    """Verify 3D displacement projection along slope movement trend and plunge."""
    # Pure horizontal movement along 90 deg (East), plunge = 0 deg
    d = project_vector_to_movement_direction(
        east_mm=10.0, north_mm=0.0, up_mm=0.0,
        trend_azimuth_deg=90.0, plunge_dip_deg=0.0
    )
    assert abs(d - 10.0) < 0.01

    # Movement dipping 30 deg downward along 180 deg (South)
    # Unit vector: E=0, N=-cos(30), U=-sin(30)
    # If ground moves South by 8.66mm and Down by 5.0mm (total 10mm along plunge)
    d2 = project_vector_to_movement_direction(
        east_mm=0.0, north_mm=8.66, up_mm=-5.0,
        trend_azimuth_deg=0.0, plunge_dip_deg=30.0  # trend North, dip 30 downward
    )
    assert abs(d2 - 10.0) < 0.05


def test_thermal_and_barometric_compensations():
    """Verify temperature and atmospheric compensation calculations."""
    # Extensometer expansion: wire expands at higher temp, artificially shortening apparent scarp opening
    raw_ext = 15.20
    corr_ext = apply_temperature_compensation(raw_ext, temperature_c=30.0, reference_temp_c=20.0)
    assert corr_ext < raw_ext

    # Piezometer barometric correction: high atmospheric pressure increases raw head reading
    raw_pz = 250.0  # kPa
    corr_pz = apply_barometric_compensation(raw_pz, barometric_pressure_kpa=102.5, baseline_baro_kpa=101.325)
    assert corr_pz < raw_pz


def test_hampel_spike_filter_and_velocity():
    """Verify spike suppression with Hampel filter and robust velocity estimation."""
    t_days = np.linspace(0, 10, 11)
    # Steady 5 mm/day velocity with an extreme electrical spike at index 5
    d = 5.0 * t_days
    d_spiked = np.copy(d)
    d_spiked[5] += 80.0  # 80 mm spike

    clean_d = apply_hampel_filter(d_spiked, window_size=5, n_sigmas=3.0)
    assert abs(clean_d[5] - d[5]) <= 5.0

    res = compute_theil_sen_velocity(t_days, clean_d)
    assert abs(res["v_mm_day"] - 5.0) < 0.2
    assert res["sigma_v_mm_day"] > 0
