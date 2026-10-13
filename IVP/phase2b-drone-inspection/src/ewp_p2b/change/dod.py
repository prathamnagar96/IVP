"""DEM of Difference calculations with an explicit propagated LoD95 gate."""

from __future__ import annotations

from typing import Dict, Tuple
import numpy as np


def lod95(sigma_before_m: float, sigma_after_m: float, registration_sigma_m: float = 0.0) -> float:
    """Return the propagated 95% level of detection in metres."""
    values = (sigma_before_m, sigma_after_m, registration_sigma_m)
    if any(not np.isfinite(value) or value < 0 for value in values):
        raise ValueError("uncertainties must be finite and non-negative")
    return float(1.96 * np.sqrt(sum(value * value for value in values)))


def dem_of_difference(
    before_m: np.ndarray,
    after_m: np.ndarray,
    sigma_before_m: float,
    sigma_after_m: float,
    registration_sigma_m: float = 0.0,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Compute DoD and suppress changes whose absolute value is below LoD95.

    NaNs remain excluded from the result. Volume is the sum of significant
    elevation change multiplied by ``cell_area_m2``.
    """
    before = np.asarray(before_m, dtype=float)
    after = np.asarray(after_m, dtype=float)
    if before.shape != after.shape:
        raise ValueError("before and after rasters must have identical shapes")
    lod = lod95(sigma_before_m, sigma_after_m, registration_sigma_m)
    difference = after - before
    significant = np.isfinite(difference) & (np.abs(difference) >= lod)
    filtered = np.where(significant, difference, np.nan)
    return filtered, {"lod95_m": lod, "significant_cells": int(significant.sum())}


def volume_change_m3(change_m: np.ndarray, cell_area_m2: float) -> float:
    """Return signed volume from a LoD-filtered change raster."""
    if not np.isfinite(cell_area_m2) or cell_area_m2 <= 0:
        raise ValueError("cell_area_m2 must be positive and finite")
    values = np.asarray(change_m, dtype=float)
    return float(np.nansum(values) * cell_area_m2)
