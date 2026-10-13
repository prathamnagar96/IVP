"""Noise floor calibration and sensor baseline estimation (Section 6)."""

from typing import Dict, Any, List
import numpy as np


class NoiseFloorEstimator:
    def __init__(self, min_baseline_points: int = 20):
        self.min_points = min_baseline_points

    def estimate_noise_floor(self, baseline_readings: np.ndarray) -> Dict[str, float]:
        """Estimate 1-sigma empirical noise floor from baseline monitoring readings."""
        if len(baseline_readings) < self.min_points:
            # Fallback to standard conservative default if baseline is short
            sigma = float(np.std(baseline_readings)) if len(baseline_readings) > 1 else 1.0
            return {
                "sigma_noise": round(max(0.5, sigma), 3),
                "is_calibrated": False,
                "sample_count": len(baseline_readings),
            }

        # Detrend baseline to compute stationary residual noise floor
        t = np.arange(len(baseline_readings))
        p = np.polyfit(t, baseline_readings, 1)
        detrended = baseline_readings - np.polyval(p, t)

        # 1-sigma standard deviation of detrended residuals
        sigma_noise = float(np.std(detrended))

        return {
            "sigma_noise": round(max(0.05, sigma_noise), 3),
            "is_calibrated": True,
            "sample_count": len(baseline_readings),
        }
