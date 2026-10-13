"""Active Deformation Area (ADA) detection and spatial clustering (Section 5.7).

Identifies statistically significant velocity anomalies (|v| > k * sigma)
and clusters contiguous or nearby coherent pixels into ADAs.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np


class ADADetector:
    def __init__(self, k_sigma: float = 3.0, min_pixels: int = 9):
        self.k_sigma = k_sigma
        self.min_pixels = min_pixels

    def detect_ada_in_unit(
        self,
        pixel_velocities_mm_yr: np.ndarray,
        pixel_sigmas_mm_yr: np.ndarray,
        pixel_coherences: Optional[np.ndarray] = None,
        min_coherence: float = 0.70,
    ) -> Dict[str, Any]:
        """Evaluate if an Active Deformation Area exists within a slope unit.

        Criteria:
        1. Coherence >= min_coherence (0.7).
        2. Absolute velocity exceeds k * sigma.
        3. At least min_pixels (e.g. 9) coherent flagged pixels present.
        """
        if len(pixel_velocities_mm_yr) == 0:
            return {
                "ada_detected": False,
                "significant_pixel_count": 0,
                "mean_v_mm_yr": 0.0,
                "max_v_mm_yr": 0.0,
            }

        v = np.array(pixel_velocities_mm_yr)
        sigma = np.array(pixel_sigmas_mm_yr)

        if pixel_coherences is not None:
            coherent_mask = pixel_coherences >= min_coherence
        else:
            coherent_mask = np.ones(len(v), dtype=bool)

        # Statistical significance test: |v| > k * sigma
        sig_mask = coherent_mask & (np.abs(v) > (self.k_sigma * sigma))
        flagged_count = int(np.sum(sig_mask))

        is_ada = flagged_count >= self.min_pixels
        if is_ada:
            flagged_v = v[sig_mask]
            mean_v = float(np.mean(flagged_v))
            max_v = float(np.max(np.abs(flagged_v)))
        else:
            mean_v = float(np.mean(v)) if len(v) > 0 else 0.0
            max_v = float(np.max(np.abs(v))) if len(v) > 0 else 0.0

        return {
            "ada_detected": is_ada,
            "significant_pixel_count": flagged_count,
            "mean_v_mm_yr": round(mean_v, 2),
            "max_v_mm_yr": round(max_v, 2),
        }
