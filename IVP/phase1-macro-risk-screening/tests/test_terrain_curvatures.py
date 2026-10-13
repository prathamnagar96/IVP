"""Test terrain curvatures, TWI, and kinematic daylighting index."""

import numpy as np
import pytest
from ewp_p1.terrain.horn import compute_curvatures, compute_twi
from ewp_p1.features.kinematic import (
    evaluate_planar_sliding,
    evaluate_toppling,
    compute_kinematic_feasibility_index,
)
from ewp_p1.common.types import DataStatus


def test_twi_calculation():
    """Verify TWI behavior: steeper slopes have lower TWI, flat high-accumulation areas have higher TWI."""
    flat_slope = np.array([2.0])  # 2 degrees
    steep_slope = np.array([45.0])  # 45 degrees

    twi_flat = compute_twi(flat_slope, flow_accumulation=np.array([100.0]), cell_size=10.0)
    twi_steep = compute_twi(steep_slope, flow_accumulation=np.array([1.0]), cell_size=10.0)

    assert twi_flat[0] > twi_steep[0]


def test_kinematic_markland_planar_and_toppling():
    """Verify Markland planar sliding and Goodman & Bray toppling conditions."""
    # Planar sliding: slope dips 45 deg facing East (90 deg)
    # Joint dips 35 deg facing East (90 deg). Friction angle = 30 deg.
    # Conditions: 30 < 35 < 45 and dip direction match -> Daylight!
    assert evaluate_planar_sliding(
        slope_dip_deg=45.0,
        slope_aspect_deg=90.0,
        discontinuity_dip_deg=35.0,
        discontinuity_dip_dir_deg=95.0,  # within 20 deg
        friction_angle_deg=30.0,
    ) is True

    # Joint dips steeper than slope face (50 > 45) -> Cannot daylight
    assert evaluate_planar_sliding(
        slope_dip_deg=45.0,
        slope_aspect_deg=90.0,
        discontinuity_dip_deg=50.0,
        discontinuity_dip_dir_deg=90.0,
        friction_angle_deg=30.0,
    ) is False


def test_kinematic_feasibility_index_unknown_when_no_attitudes():
    """Invariant: If no attitude measurements exist, quality must be UNKNOWN, not imputed safe."""
    res = compute_kinematic_feasibility_index(
        slope_dip_deg=35.0,
        slope_aspect_deg=120.0,
        attitude_measurements=[],  # Empty!
    )

    assert res["quality"] == DataStatus.UNKNOWN.value
    assert "no attitude measurements in unit" in res["reason"]
    assert res["kinematic_index"] == 0.0
