"""Displacement vector projection and thermal/barometric sensor compensation (Section 6)."""

from typing import Dict, Any, Optional
import numpy as np


def project_vector_to_movement_direction(
    east_mm: float,
    north_mm: float,
    up_mm: float,
    trend_azimuth_deg: float,
    plunge_dip_deg: float,
) -> float:
    """Project 3D GNSS ENU displacement vector onto slope movement direction.

    trend_azimuth_deg: direction of displacement vector clockwise from North (0..360).
    plunge_dip_deg: downward dip of movement vector (0 = horizontal, 90 = vertical).
    Returns:
        Scalar displacement along movement direction (positive = forward/downslope movement).
    """
    alpha = np.radians(trend_azimuth_deg)
    beta = np.radians(plunge_dip_deg)

    # Unit vector along movement direction:
    # E = sin(alpha) * cos(beta)
    # N = cos(alpha) * cos(beta)
    # U = -sin(beta)  (downward motion)
    u_e = np.sin(alpha) * np.cos(beta)
    u_n = np.cos(alpha) * np.cos(beta)
    u_u = -np.sin(beta)

    d_along = east_mm * u_e + north_mm * u_n + up_mm * u_u
    return float(round(d_along, 3))


def apply_temperature_compensation(
    raw_displacement_mm: float,
    temperature_c: float,
    reference_temp_c: float = 20.0,
    thermal_expansion_coeff_mm_per_c: float = 0.012,  # Typical invar / stainless wire
) -> float:
    """Correct extensometer or tiltmeter readings for diurnal thermal expansion."""
    delta_t = temperature_c - reference_temp_c
    correction = thermal_expansion_coeff_mm_per_c * delta_t
    corrected = raw_displacement_mm - correction
    return float(round(corrected, 3))


def apply_barometric_compensation(
    raw_pore_pressure_kpa: float,
    barometric_pressure_kpa: float,
    baseline_baro_kpa: float = 101.325,
) -> float:
    """Compensate non-vented vibrating wire piezometer readings for atmospheric pressure fluctuations."""
    delta_baro = barometric_pressure_kpa - baseline_baro_kpa
    corrected_p = raw_pore_pressure_kpa - delta_baro
    return float(round(corrected_p, 3))
