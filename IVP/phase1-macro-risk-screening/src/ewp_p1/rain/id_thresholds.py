"""Rainfall Intensity-Duration (I-D) thresholds and classification (Section 5.6).

Evaluates I = alpha * D^(-beta) curves (e.g., Caine 1980, Guzzetti et al. 2008, local calibrated)
to categorize storm events into NORMAL, WATCH, EXCEEDED, or EXTREME.
"""

from typing import Dict, Any, Optional
from ..common.types import RainClass


class IDThresholdEvaluator:
    def __init__(
        self,
        alpha: float = 14.82,  # Caine 1980 default
        beta: float = 0.39,
        watch_multiplier: float = 0.70,
        extreme_multiplier: float = 1.50,
    ):
        self.alpha = alpha
        self.beta = beta
        self.watch_multiplier = watch_multiplier
        self.extreme_multiplier = extreme_multiplier

    def compute_threshold_intensity(self, duration_h: float) -> float:
        """Calculate critical intensity in mm/h for a given storm duration D (hours)."""
        d = max(0.1, duration_h)
        return float(self.alpha * (d ** (-self.beta)))

    def classify_event(
        self, duration_h: float, intensity_mm_h: float
    ) -> Dict[str, Any]:
        """Classify rainfall event against I-D curve."""
        i_crit = self.compute_threshold_intensity(duration_h)
        ratio = intensity_mm_h / i_crit if i_crit > 0 else 0.0

        if ratio >= self.extreme_multiplier:
            rain_class = RainClass.EXTREME
        elif ratio >= 1.0:
            rain_class = RainClass.EXCEEDED
        elif ratio >= self.watch_multiplier:
            rain_class = RainClass.WATCH
        else:
            rain_class = RainClass.NORMAL

        return {
            "rain_class": rain_class.value,
            "threshold_intensity_mm_h": round(i_crit, 2),
            "observed_intensity_mm_h": round(intensity_mm_h, 2),
            "exceedance_ratio": round(ratio, 3),
        }
