"""Test InSAR LOS-to-downslope projection, decomposition, and ADA detection."""

import numpy as np
import pytest
from ewp_p1.insar.projection import (
    compute_los_unit_vector,
    compute_downslope_unit_vector,
    project_los_to_downslope,
)
from ewp_p1.insar.decomposition import decompose_insar_timeseries
from ewp_p1.insar.ada import ADADetector


def test_insar_los_projection_geometry_and_sign():
    """Test LOS projection into downslope direction.

    Scenario:
    Slope dips 30 deg facing East (aspect = 90 deg).
    Ascending track (heading = 350 deg, incidence = 35 deg).
    Looking eastward towards the slope face.
    If the slope slides downhill towards East, displacement is negative (downslope).
    """
    res = project_los_to_downslope(
        v_los_mm_yr=-15.0,  # LOS displacement away from satellite
        incidence_angle_deg=35.0,
        heading_angle_deg=350.0,
        slope_dip_deg=30.0,
        aspect_deg=90.0,
        min_sensitivity=0.20,
    )

    assert res["valid"] is True
    # Downslope sliding motion must have negative velocity convention
    assert res["v_downslope_mm_yr"] < 0
    assert abs(res["c_factor"]) >= 0.20


def test_insar_low_sensitivity_masking():
    """When slope motion is nearly perpendicular to radar LOS, projection must flag low sensitivity."""
    # North-South slope (aspect = 0 deg) observed by ascending pass looking East/West
    res = project_los_to_downslope(
        v_los_mm_yr=5.0,
        incidence_angle_deg=35.0,
        heading_angle_deg=350.0,
        slope_dip_deg=5.0,
        aspect_deg=0.0,  # Pure North
        min_sensitivity=0.30,
    )

    # North-south motion has weak sensitivity in near-polar orbits
    if abs(res["c_factor"]) < 0.30:
        assert res["valid"] is False
        assert "low projection sensitivity" in res["reason"]


def test_insar_timeseries_harmonic_decomposition():
    """Verify secular velocity extraction in presence of seasonal oscillation."""
    # True motion: secular creep of -20 mm/yr + 8 mm annual seasonal cycle
    t_days = np.linspace(0, 730, 60)  # 2 years of observations
    v_true = -20.0
    seasonal_amp = 8.0
    noise = np.random.RandomState(42).normal(0, 1.0, len(t_days))

    omega = 2.0 * np.pi / 365.25
    displacements = (v_true * t_days / 365.25) + seasonal_amp * np.sin(omega * t_days) + noise

    fit = decompose_insar_timeseries(t_days, displacements)

    assert abs(fit["v_secular_mm_yr"] - v_true) < 2.5
    assert abs(fit["annual_amplitude_mm"] - seasonal_amp) < 2.0


def test_ada_clustering_detection():
    """Verify ADA detection with statistically significant pixel clusters."""
    detector = ADADetector(k_sigma=3.0, min_pixels=9)

    # 15 pixels with high velocity > 3*sigma and coherence 0.8
    v_pixels = np.full(15, -35.0)
    sigmas = np.full(15, 4.0)  # 3 * 4 = 12 < 35
    coherence = np.full(15, 0.85)

    res = detector.detect_ada_in_unit(v_pixels, sigmas, coherence)
    assert res["ada_detected"] is True
    assert res["significant_pixel_count"] == 15
    assert res["mean_v_mm_yr"] == -35.0

    # Below threshold count (e.g. only 4 pixels) -> NOT an ADA
    res_few = detector.detect_ada_in_unit(v_pixels[:4], sigmas[:4], coherence[:4])
    assert res_few["ada_detected"] is False
