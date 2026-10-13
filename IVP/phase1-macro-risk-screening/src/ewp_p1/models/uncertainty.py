"""Uncertainty estimation and interval widening (Sections 5.4, 5.9).

Bootstrap or model-based quantile intervals with uncertainty widening
when critical features are DEGRADED or UNKNOWN.
"""

from typing import Tuple, List, Optional
import numpy as np
from ..common.types import DataStatus


def estimate_uncertainty_interval(
    s_score: float,
    model_predictions_ensemble: Optional[np.ndarray] = None,
    data_status: DataStatus = DataStatus.OK,
    base_spread: float = 0.08,
) -> Tuple[float, float]:
    """Calculate lower and upper uncertainty bounds [s_lo, s_hi] around susceptibility score S.

    Invariant handling: If data_status is UNKNOWN or DEGRADED, the uncertainty interval widens significantly.
    """
    if model_predictions_ensemble is not None and len(model_predictions_ensemble) > 0:
        p10 = float(np.percentile(model_predictions_ensemble, 10))
        p90 = float(np.percentile(model_predictions_ensemble, 90))
        lo = min(s_score, p10)
        hi = max(s_score, p90)
    else:
        lo = max(0.0, s_score - base_spread)
        hi = min(1.0, s_score + base_spread)

    # Widen interval according to data quality
    if data_status == DataStatus.UNKNOWN:
        # Significant uncertainty widening: expand interval by at least +/- 0.15
        lo = max(0.0, lo - 0.15)
        hi = min(1.0, hi + 0.15)
    elif data_status == DataStatus.DEGRADED:
        lo = max(0.0, lo - 0.08)
        hi = min(1.0, hi + 0.08)

    return round(float(lo), 4), round(float(hi), 4)
