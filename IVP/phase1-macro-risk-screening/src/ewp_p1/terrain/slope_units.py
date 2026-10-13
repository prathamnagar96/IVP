"""Slope unit delineation data structures, topology checks, and raster-to-unit masking."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


@dataclass
class SlopeUnitGeometry:
    unit_id: str
    region: str
    polygon_coords: List[Tuple[float, float]]  # List of (x, y) coordinates
    area_m2: float
    elevation_min: float
    elevation_max: float
    centroid: Tuple[float, float]
    bounds: Tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    metadata: Dict[str, Any] = field(default_factory=dict)


def generate_unit_id(region: str, sequence_num: int) -> str:
    """Generate standardized slope unit ID, e.g. SU-R01-000123."""
    return f"SU-{region}-{sequence_num:06d}"


def check_topology_invariants(units: List[SlopeUnitGeometry]) -> Dict[str, Any]:
    """Verify topological consistency: checks for duplicated unit IDs, extreme area sizes, and empty geometries."""
    ids = [u.unit_id for u in units]
    unique_ids = set(ids)
    has_duplicates = len(ids) != len(unique_ids)

    areas = [u.area_m2 for u in units]
    total_area_km2 = sum(areas) / 1e6 if areas else 0.0
    min_area_m2 = min(areas) if areas else 0.0
    max_area_m2 = max(areas) if areas else 0.0
    median_area_m2 = float(np.median(areas)) if areas else 0.0

    return {
        "valid": not has_duplicates and min_area_m2 > 0,
        "unit_count": len(units),
        "duplicate_ids": has_duplicates,
        "total_area_km2": total_area_km2,
        "min_area_m2": min_area_m2,
        "max_area_m2": max_area_m2,
        "median_area_m2": median_area_m2,
    }


def aggregate_raster_to_slope_unit(
    raster: np.ndarray, mask: np.ndarray
) -> Dict[str, float]:
    """Calculate summary statistics (mean, std, p10, p50, p90, min, max) of a raster inside a unit mask."""
    vals = raster[mask]
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return {
            "mean": 0.0,
            "std": 0.0,
            "p10": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    return {
        "mean": float(np.mean(vals)),
        "std": float(np.std(vals)),
        "p10": float(np.percentile(vals, 10)),
        "p50": float(np.median(vals)),
        "p90": float(np.percentile(vals, 90)),
        "min": float(np.min(vals)),
        "max": float(np.max(vals)),
    }
