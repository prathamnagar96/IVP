"""Sentinel-2 optical feature extraction, vegetation indices, burn scars, and quality checks."""

from typing import Dict, Any, Optional
import numpy as np
from ..common.types import DataStatus


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Calculate Normalized Difference Vegetation Index: (NIR - Red) / (NIR + Red)."""
    denom = nir + red
    denom = np.where(denom == 0, 1e-6, denom)
    ndvi = (nir - red) / denom
    return np.clip(ndvi, -1.0, 1.0)


def compute_dnbr(nbr_pre: np.ndarray, nbr_post: np.ndarray) -> np.ndarray:
    """Calculate differenced Normalized Burn Ratio (dNBR) for fire burn scar detection."""
    return nbr_pre - nbr_post


def evaluate_optical_quality(
    days_since_last_clear_scene: int,
    clear_scene_count_in_window: int,
    max_gap_days: int = 30,
) -> Dict[str, Any]:
    """Check optical data freshness and quality according to Section 5.9.

    - UNKNOWN if no clear observation within max_gap_days.
    - DEGRADED if single clear observation in window.
    - OK if >= 2 clear observations and within max_gap_days.
    """
    if days_since_last_clear_scene > max_gap_days:
        return {
            "status": DataStatus.UNKNOWN.value,
            "reason": f"no clear optical observation within {max_gap_days} days (current gap: {days_since_last_clear_scene}d)",
        }
    elif clear_scene_count_in_window < 2:
        return {
            "status": DataStatus.DEGRADED.value,
            "reason": f"single clear optical observation in monitoring window (count={clear_scene_count_in_window})",
        }
    return {
        "status": DataStatus.OK.value,
        "reason": "",
    }
