"""Horn (1981) finite-difference terrain derivatives and topographic metrics."""

import numpy as np
from typing import Tuple, Dict, Any, Optional


def compute_horn_derivatives(
    dem: np.ndarray, cell_size_x: float, cell_size_y: Optional[float] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute dz/dx and dz/dy using Horn's 1981 3x3 finite-difference algorithm.

    Formula (with grid points numbered 1 to 9):
        [z1, z2, z3]   (row - 1: North if cartesian, or top)
        [z4, z5, z6]   (row 0: Center)
        [z7, z8, z9]   (row + 1: South if cartesian, or bottom)

    dz_dx = ((z3 + 2*z6 + z9) - (z1 + 2*z4 + z7)) / (8 * dx)
    dz_dy = ((z7 + 2*z8 + z9) - (z1 + 2*z2 + z3)) / (8 * dy)  (or standard gradient)
    """
    if cell_size_y is None:
        cell_size_y = cell_size_x

    rows, cols = dem.shape
    dz_dx = np.zeros_like(dem, dtype=np.float64)
    dz_dy = np.zeros_like(dem, dtype=np.float64)

    # Internal 3x3 neighborhood slices
    z1 = dem[:-2, :-2]
    z2 = dem[:-2, 1:-1]
    z3 = dem[:-2, 2:]

    z4 = dem[1:-1, :-2]
    z5 = dem[1:-1, 1:-1]
    z6 = dem[1:-1, 2:]

    z7 = dem[2:, :-2]
    z8 = dem[2:, 1:-1]
    z9 = dem[2:, 2:]

    # Finite difference calculation
    dx_diff = (z3 + 2.0 * z6 + z9) - (z1 + 2.0 * z4 + z7)
    dy_diff = (z7 + 2.0 * z8 + z9) - (z1 + 2.0 * z2 + z3)

    dz_dx[1:-1, 1:-1] = dx_diff / (8.0 * cell_size_x)
    dz_dy[1:-1, 1:-1] = dy_diff / (8.0 * cell_size_y)

    # Edge padding with nearest valid interior cells
    dz_dx[0, :] = dz_dx[1, :]
    dz_dx[-1, :] = dz_dx[-2, :]
    dz_dx[:, 0] = dz_dx[:, 1]
    dz_dx[:, -1] = dz_dx[:, -2]

    dz_dy[0, :] = dz_dy[1, :]
    dz_dy[-1, :] = dz_dy[-2, :]
    dz_dy[:, 0] = dz_dy[:, 1]
    dz_dy[:, -1] = dz_dy[:, -2]

    return dz_dx, dz_dy


def compute_slope_aspect(
    dem: np.ndarray, cell_size_x: float, cell_size_y: Optional[float] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate slope in degrees and compass aspect in degrees (0=N, 90=E, 180=S, 270=W)."""
    dz_dx, dz_dy = compute_horn_derivatives(dem, cell_size_x, cell_size_y)

    gradient_mag = np.sqrt(dz_dx**2 + dz_dy**2)
    slope_deg = np.degrees(np.arctan(gradient_mag))

    # Aspect: compass degrees clockwise from North
    # When y increases downwards (standard image/raster coordinate system):
    # dz_dy > 0 means slope falls downwards (+row / South).
    aspect_rad = np.arctan2(dz_dy, -dz_dx)
    aspect_deg = (np.degrees(aspect_rad) + 90.0) % 360.0

    # Flat areas (gradient ~ 0) have undefined/0 aspect
    flat_mask = gradient_mag < 1e-7
    aspect_deg[flat_mask] = 0.0

    return slope_deg, aspect_deg


def compute_curvatures(
    dem: np.ndarray, cell_size: float
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute planform curvature and profile curvature using 3x3 polynomial approximations."""
    rows, cols = dem.shape
    p = np.zeros_like(dem, dtype=np.float64)
    q = np.zeros_like(dem, dtype=np.float64)
    r = np.zeros_like(dem, dtype=np.float64)
    s = np.zeros_like(dem, dtype=np.float64)
    t = np.zeros_like(dem, dtype=np.float64)

    z1 = dem[:-2, :-2]
    z2 = dem[:-2, 1:-1]
    z3 = dem[:-2, 2:]
    z4 = dem[1:-1, :-2]
    z5 = dem[1:-1, 1:-1]
    z6 = dem[1:-1, 2:]
    z7 = dem[2:, :-2]
    z8 = dem[2:, 1:-1]
    z9 = dem[2:, 2:]

    L = cell_size
    p[1:-1, 1:-1] = (z3 + z6 + z9 - z1 - z4 - z7) / (6.0 * L)
    q[1:-1, 1:-1] = (z1 + z2 + z3 - z7 - z8 - z9) / (6.0 * L)
    r[1:-1, 1:-1] = (z1 + z3 + z4 + z6 + z7 + z9 - 2.0 * (z2 + z5 + z8)) / (3.0 * L**2)
    s[1:-1, 1:-1] = (z3 + z7 - z1 - z9) / (4.0 * L**2)
    t[1:-1, 1:-1] = (z1 + z2 + z3 + z7 + z8 + z9 - 2.0 * (z4 + z5 + z6)) / (3.0 * L**2)

    denom = p**2 + q**2
    safe_denom = np.where(denom < 1e-8, 1e-8, denom)

    # Profile curvature (along maximum slope)
    profile_curv = -(p**2 * r + 2.0 * p * q * s + q**2 * t) / (safe_denom * (1.0 + denom)**1.5)

    # Plan curvature (perpendicular to slope direction)
    plan_curv = -(q**2 * r - 2.0 * p * q * s + p**2 * t) / (safe_denom**1.5)

    profile_curv[denom < 1e-8] = 0.0
    plan_curv[denom < 1e-8] = 0.0

    return plan_curv, profile_curv


def compute_twi(
    slope_deg: np.ndarray, flow_accumulation: Optional[np.ndarray] = None, cell_size: float = 30.0
) -> np.ndarray:
    """Compute Topographic Wetness Index: TWI = ln(a / tan(beta))."""
    slope_rad = np.radians(np.clip(slope_deg, 0.1, 89.9))
    tan_beta = np.tan(slope_rad)

    if flow_accumulation is None:
        # Fallback to local approximation if full grid flow accumulation not supplied
        a = cell_size
    else:
        a = np.clip(flow_accumulation * cell_size, cell_size, None)

    twi = np.log(a / tan_beta)
    return np.clip(twi, 0.0, 30.0)


def create_synthetic_plane(
    slope_deg: float,
    aspect_deg: float,
    shape: Tuple[int, int] = (50, 50),
    cell_size: float = 10.0,
    base_elevation: float = 1000.0,
) -> np.ndarray:
    """Generate an exact planar synthetic DEM tilted at a specific slope and aspect."""
    rows, cols = shape
    theta = np.radians(slope_deg)
    phi = np.radians(aspect_deg)

    # Normal vector components
    # dz/dx = sin(theta) * sin(phi)
    # dz/dy = -sin(theta) * cos(phi)  (if row increases southward)
    grad_mag = np.tan(theta)
    # Aspect angle clockwise from North:
    # dz/dx points East, dz/dy points South
    gx = grad_mag * np.sin(phi)
    gy = grad_mag * np.cos(phi)

    x = np.arange(cols) * cell_size
    y = np.arange(rows) * cell_size
    xx, yy = np.meshgrid(x, y)

    dem = base_elevation + gx * xx + gy * yy
    return dem
