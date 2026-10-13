"""Rolling rainfall accumulations and Antecedent Precipitation Index (API)."""

from typing import List, Dict, Any, Union
import numpy as np


class RainfallAccumulator:
    def __init__(self, api_window_days: int = 14, api_decay: float = 0.85):
        self.api_window_days = api_window_days
        self.api_decay = api_decay

    def compute_rolling_accumulations(
        self, hourly_series: Union[List[float], np.ndarray]
    ) -> Dict[str, float]:
        """Compute rolling rainfall sums for standard intervals: 1h, 3h, 6h, 24h, 72h."""
        arr = np.array(hourly_series, dtype=np.float64)
        n = len(arr)
        if n == 0:
            return {"1h": 0.0, "3h": 0.0, "6h": 0.0, "24h": 0.0, "72h": 0.0}

        def get_sum(hours: int) -> float:
            if n < hours:
                return float(np.sum(arr))
            return float(np.sum(arr[-hours:]))

        return {
            "1h": round(get_sum(1), 2),
            "3h": round(get_sum(3), 2),
            "6h": round(get_sum(6), 2),
            "24h": round(get_sum(24), 2),
            "72h": round(get_sum(72), 2),
        }

    def compute_api(self, daily_rainfall_series: Union[List[float], np.ndarray]) -> float:
        """Calculate Antecedent Precipitation Index (API): API_t = sum_{k=1..W} (P_{t-k} * alpha^k).

        daily_rainfall_series: array of past days up to today (most recent day at index -1).
        """
        arr = np.array(daily_rainfall_series, dtype=np.float64)
        if len(arr) == 0:
            return 0.0

        # Most recent day is index -1, previous day is -2, etc.
        w = min(len(arr), self.api_window_days)
        recent_days = arr[-w:]

        api = 0.0
        # k goes from 1 (yesterday) to w
        for k in range(1, w + 1):
            p = recent_days[-k]
            decay_factor = self.api_decay ** k
            api += p * decay_factor

        return round(float(api), 2)
