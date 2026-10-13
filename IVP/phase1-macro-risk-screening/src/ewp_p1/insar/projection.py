"""InSAR Line-of-Sight (LOS) to downslope velocity projection (Section 5.7, 9).

Projects satellite LOS velocity into the direction of steepest slope gradient
accounting for flight heading, incidence angle, and terrain geometry.
"""

from typing import Tuple, Dict, Any, Optional
import numpy as np


def compute_los_unit_vector(
    incidence_angle_deg: float, heading_angle_deg: float
) -> np.ndarray:
    """Compute the 3D LOS unit vector pointing from ground to sensor in East, North, Up (ENU).

    incidence_angle: angle between upward vertical and radar LOS (degrees).
    heading_angle: satellite flight direction clockwise from North (degrees, ~348-350 for Ascending, ~190-192 for Descending).
    Radar looks to the right of flight direction (look angle = heading - 90).
    """
    theta = np.radians(incidence_angle_deg)
    # Right-looking radar: look azimuth phi
    # Ascending (heading ~ 350): look is East-facing (~ 80 deg)
    # Descending (heading ~ 190): look is West-facing (~ 260 deg)
    look_azimuth_deg = (heading_angle_deg + 90.0) % 360.0
    phi = np.radians(look_azimuth_deg)

    # Unit vector pointing from target to satellite (LOS):
    # E = -sin(theta) * sin(phi)
    # N = -sin(theta) * cos(phi)
    # U = cos(theta)
    u_e = -np.sin(theta) * np.sin(phi)
    u_n = -np.sin(theta) * np.cos(phi)
    u_u = np.cos(theta)

    vec = np.array([u_e, u_n, u_u], dtype=np.float64)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def compute_downslope_unit_vector(
    slope_dip_deg: float, aspect_deg: float
) -> np.ndarray:
    """Compute 3D unit vector pointing downslope along terrain gradient in ENU coordinates.

    slope_dip: slope inclination in degrees (0 = flat, 90 = vertical).
    aspect: direction of steepest descent clockwise from North (degrees).
    """
    beta = np.radians(slope_dip_deg)
    psi = np.radians(aspect_deg)

    # Downslope vector components:
    # E = sin(psi) * cos(beta)
    # N = cos(psi) * cos(beta)
    # U = -sin(beta)  (downward motion)
    u_e = np.sin(psi) * np.cos(beta)
    u_n = np.cos(psi) * np.cos(beta)
    u_u = -np.sin(beta)

    vec = np.array([u_e, u_n, u_u], dtype=np.float64)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec


def project_los_to_downslope(
    v_los_mm_yr: float,
    incidence_angle_deg: float,
    heading_angle_deg: float,
    slope_dip_deg: float,
    aspect_deg: float,
    min_sensitivity: float = 0.20,
) -> Dict[str, Any]:
    """Project single geometry LOS velocity into slope-parallel velocity v_slope.

    Projection sensitivity factor: C = dot(u_los, u_slope).
    v_slope = v_los / C.

    If |C| < min_sensitivity, geometry is unfavorable (LOS is nearly perpendicular
    to the slope), so projection is masked to prevent noise amplification.
    Convention: Negative v_slope indicates downslope sliding motion.
    """
    u_los = compute_los_unit_vector(incidence_angle_deg, heading_angle_deg)
    u_slope = compute_downslope_unit_vector(slope_dip_deg, aspect_deg)

    # Dot product projection factor
    c_factor = float(np.dot(u_los, u_slope))

    if abs(c_factor) < min_sensitivity:
        return {
            "v_downslope_mm_yr": 0.0,
            "c_factor": round(c_factor, 4),
            "valid": False,
            "reason": f"low projection sensitivity (|C|={abs(c_factor):.3f} < {min_sensitivity})",
        }

    # Velocity in downslope direction (negative indicates downward/downslope displacement)
    # Note: When slope slides downslope, target moves along u_slope.
    # Displacement along LOS = (target_displacement) * dot(u_los, u_slope).
    v_downslope = -abs(v_los_mm_yr / c_factor) if (v_los_mm_yr * c_factor > 0 or v_los_mm_yr < 0) else (v_los_mm_yr / c_factor)

    return {
        "v_downslope_mm_yr": round(float(v_downslope), 2),
        "c_factor": round(c_factor, 4),
        "valid": True,
        "reason": "",
    }
