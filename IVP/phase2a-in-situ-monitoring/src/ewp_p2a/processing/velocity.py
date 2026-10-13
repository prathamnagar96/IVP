"""Velocity and acceleration calculation using Theil-Sen estimators and Hampel spike filtering."""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from scipy import stats


def apply_hampel_filter(
    values: np.ndarray, window_size: int = 5, n_sigmas: float = 3.0
) -> np.ndarray:
    """Hampel filter for identifying and cleaning outliers/spikes using median and MAD."""
    n = len(values)
    clean_vals = np.copy(values)
    k = 1.4826  # Scale factor for normal distribution consistency

    half_w = window_size // 2
    for i in range(n):
        low = max(0, i - half_w)
        high = min(n, i + half_w + 1)
        sub = values[low:high]
        med = np.median(sub)
        mad = np.median(np.abs(sub - med))
        threshold = n_sigmas * k * mad

        if np.abs(values[i] - med) > threshold and threshold > 1e-6:
            clean_vals[i] = med

    return clean_vals


def compute_theil_sen_velocity(
    time_days: np.ndarray, displacements_mm: np.ndarray
) -> Dict[str, float]:
    """Calculate robust velocity (mm/day) and standard error using Theil-Sen estimator.

    Returns:
        dict with v_mm_day, sigma_v_mm_day, intercept.
    """
    if len(time_days) < 3:
        # Minimum points required for meaningful Theil-Sen
        if len(time_days) == 2:
            dt = time_days[1] - time_days[0]
            v = (displacements_mm[1] - displacements_mm[0]) / dt if dt > 0 else 0.0
            return {"v_mm_day": float(round(v, 3)), "sigma_v_mm_day": 1.0, "intercept": 0.0}
        return {"v_mm_day": 0.0, "sigma_v_mm_day": 0.0, "intercept": 0.0}

    # Use scipy Theil-Sen estimator
    res = stats.theilslopes(displacements_mm, time_days, alpha=0.95)
    slope = float(res.slope)
    low_slope = float(res.low_slope)
    high_slope = float(res.high_slope)
    intercept = float(res.intercept)

    # Uncertainty approximation from 95% confidence bounds
    sigma_v = float((high_slope - low_slope) / (2.0 * 1.96))

    return {
        "v_mm_day": round(slope, 3),
        "sigma_v_mm_day": round(max(0.01, sigma_v), 3),
        "intercept": round(intercept, 3),
    }


def compute_acceleration(
    v1_mm_day: float, v2_mm_day: float, dt_days: float
) -> float:
    """Calculate acceleration in mm/day^2 between two successive velocity windows."""
    if dt_days <= 0:
        return 0.0
    return float(round((v2_mm_day - v1_mm_day) / dt_days, 3))
