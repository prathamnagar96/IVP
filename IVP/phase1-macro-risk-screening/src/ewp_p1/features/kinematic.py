"""Kinematic-feasibility index calculator using Markland (1972) daylighting tests."""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from ..common.types import DataStatus


def evaluate_planar_sliding(
    slope_dip_deg: float,
    slope_aspect_deg: float,
    discontinuity_dip_deg: float,
    discontinuity_dip_dir_deg: float,
    friction_angle_deg: float = 30.0,
    aspect_tolerance_deg: float = 20.0,
) -> bool:
    """Markland planar sliding test.

    Conditions:
    1. Discontinuity dip direction is within +/- aspect_tolerance_deg of slope aspect (face direction).
    2. Discontinuity dip > friction_angle_deg (kinematically capable of sliding).
    3. Discontinuity dip < slope_dip_deg (discontinuity daylights on slope face).
    """
    # Angular difference in dip direction vs slope aspect
    diff = abs((discontinuity_dip_dir_deg - slope_aspect_deg + 180.0) % 360.0 - 180.0)
    aspect_match = diff <= aspect_tolerance_deg

    daylights = discontinuity_dip_deg < slope_dip_deg
    friction_exceeded = discontinuity_dip_deg > friction_angle_deg

    return bool(aspect_match and daylights and friction_exceeded)


def evaluate_toppling(
    slope_dip_deg: float,
    slope_aspect_deg: float,
    discontinuity_dip_deg: float,
    discontinuity_dip_dir_deg: float,
    friction_angle_deg: float = 30.0,
    tolerance_deg: float = 30.0,
) -> bool:
    """Goodman & Bray test for direct/flexural toppling.

    Conditions:
    1. Strike of discontinuity is sub-parallel to slope strike (dip directions opposite, diff ~ 180 deg +/- tolerance).
    2. Discontinuity dips steeply into the slope face: (90 - discontinuity_dip) + friction_angle <= slope_dip.
    """
    diff = abs((discontinuity_dip_dir_deg - slope_aspect_deg + 180.0) % 360.0 - 180.0)
    opposite_dir = abs(diff - 180.0) <= tolerance_deg
    steep_condition = (90.0 - discontinuity_dip_deg) + friction_angle_deg <= slope_dip_deg

    return bool(opposite_dir and steep_condition)


def compute_kinematic_feasibility_index(
    slope_dip_deg: float,
    slope_aspect_deg: float,
    attitude_measurements: Optional[List[Tuple[float, float]]] = None,  # list of (dip, dip_dir)
    friction_angle_deg: float = 30.0,
) -> Dict[str, Any]:
    """Calculate the share of structural sets daylighting on the slope face.

    If no structural attitude measurements exist in the unit:
    returns kinematic_index=0.0, quality=UNKNOWN, reason="no attitude measurements in unit".
    """
    if attitude_measurements is None or len(attitude_measurements) == 0:
        return {
            "kinematic_index": 0.0,
            "planar_count": 0,
            "toppling_count": 0,
            "total_measured": 0,
            "quality": DataStatus.UNKNOWN.value,
            "reason": "no attitude measurements in unit",
        }

    total = len(attitude_measurements)
    planar_hits = 0
    toppling_hits = 0

    for dip, dip_dir in attitude_measurements:
        if evaluate_planar_sliding(
            slope_dip_deg, slope_aspect_deg, dip, dip_dir, friction_angle_deg
        ):
            planar_hits += 1
        if evaluate_toppling(
            slope_dip_deg, slope_aspect_deg, dip, dip_dir, friction_angle_deg
        ):
            toppling_hits += 1

    feasible_hits = max(planar_hits, toppling_hits)
    index = feasible_hits / total

    # Sparse measurements check (< 5 measurements is DEGRADED)
    if total < 5:
        quality = DataStatus.DEGRADED.value
        reason = f"sparse structural measurements (count={total} < 5)"
    else:
        quality = DataStatus.OK.value
        reason = ""

    return {
        "kinematic_index": round(index, 4),
        "planar_count": planar_hits,
        "toppling_count": toppling_hits,
        "total_measured": total,
        "quality": quality,
        "reason": reason,
    }
