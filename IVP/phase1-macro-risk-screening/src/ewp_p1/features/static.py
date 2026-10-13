"""Static terrain, geological, and contextual feature extraction for slope units."""

from typing import Dict, Any, List, Optional
import numpy as np
from ..common.types import DataStatus


class LithologyLookup:
    def __init__(self, ratings_config: Optional[Dict[str, Any]] = None):
        self.ratings = {}
        self.default_rating = 0.50
        if ratings_config:
            self.default_rating = ratings_config.get("default_rating", 0.50)
            units = ratings_config.get("units", {})
            for unit_name, details in units.items():
                self.ratings[unit_name] = details.get("rating", self.default_rating)

    def get_rating(self, lithology_name: str) -> float:
        return self.ratings.get(lithology_name, self.default_rating)


def compute_static_features_for_unit(
    unit_id: str,
    slope_stats: Dict[str, float],
    aspect_stats: Dict[str, float],
    plan_curv_stats: Dict[str, float],
    profile_curv_stats: Dict[str, float],
    relative_relief_m: float,
    twi_mean: float,
    distance_to_stream_m: float,
    distance_to_road_m: float,
    distance_to_fault_m: float,
    mean_annual_rainfall_mm: float,
    seismic_pga_g: float,
    lithology_rating: float,
    soil_depth_proxy_m: float,
    land_cover_fractions: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compile static feature dictionary for a slope unit."""
    features = {
        "unit_id": unit_id,
        "slope_mean": slope_stats.get("mean", 0.0),
        "slope_std": slope_stats.get("std", 0.0),
        "slope_p10": slope_stats.get("p10", 0.0),
        "slope_p50": slope_stats.get("p50", 0.0),
        "slope_p90": slope_stats.get("p90", 0.0),
        "aspect_mean": aspect_stats.get("mean", 0.0),
        "plan_curv_mean": plan_curv_stats.get("mean", 0.0),
        "profile_curv_mean": profile_curv_stats.get("mean", 0.0),
        "relative_relief_m": float(relative_relief_m),
        "twi_mean": float(twi_mean),
        "distance_to_stream_m": float(distance_to_stream_m),
        "distance_to_road_m": float(distance_to_road_m),
        "distance_to_fault_m": float(distance_to_fault_m),
        "mean_annual_rainfall_mm": float(mean_annual_rainfall_mm),
        "seismic_pga_g": float(seismic_pga_g),
        "lithology_rating": float(lithology_rating),
        "soil_depth_proxy_m": float(soil_depth_proxy_m),
    }

    if land_cover_fractions:
        for lc_class, frac in land_cover_fractions.items():
            features[f"lc_frac_{lc_class}"] = float(frac)

    return features
