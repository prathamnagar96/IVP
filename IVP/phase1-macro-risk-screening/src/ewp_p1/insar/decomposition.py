"""InSAR time-series decomposition into secular linear trend and seasonal harmonics."""

from typing import Dict, Any, Tuple
import numpy as np


def decompose_insar_timeseries(
    time_days: np.ndarray, displacements_mm: np.ndarray
) -> Dict[str, Any]:
    """Fit secular velocity and annual + semi-annual seasonal oscillations using OLS.

    Model:
        d(t) = v * (t/365.25) + A1*cos(w*t) + B1*sin(w*t) + A2*cos(2w*t) + B2*sin(2w*t) + c
    where w = 2*pi / 365.25.
    """
    t = np.array(time_days, dtype=np.float64)
    y = np.array(displacements_mm, dtype=np.float64)

    if len(t) < 8:
        # Not enough points for harmonic inversion
        v_linear = float(np.polyfit(t / 365.25, y, 1)[0]) if len(t) >= 2 else 0.0
        return {
            "v_secular_mm_yr": round(v_linear, 2),
            "annual_amplitude_mm": 0.0,
            "semi_annual_amplitude_mm": 0.0,
            "residual_rmse_mm": 0.0,
        }

    omega = 2.0 * np.pi / 365.25
    t_yr = t / 365.25

    # Design matrix
    G = np.column_stack([
        t_yr,
        np.cos(omega * t),
        np.sin(omega * t),
        np.cos(2.0 * omega * t),
        np.sin(2.0 * omega * t),
        np.ones_like(t),
    ])

    coeffs, residuals, rank, s = np.linalg.lstsq(G, y, rcond=None)

    v_secular = coeffs[0]
    amp_annual = np.hypot(coeffs[1], coeffs[2])
    amp_semi = np.hypot(coeffs[3], coeffs[4])

    pred = G @ coeffs
    rmse = np.sqrt(np.mean((y - pred) ** 2))

    return {
        "v_secular_mm_yr": round(float(v_secular), 2),
        "annual_amplitude_mm": round(float(amp_annual), 2),
        "semi_annual_amplitude_mm": round(float(amp_semi), 2),
        "residual_rmse_mm": round(float(rmse), 2),
    }
