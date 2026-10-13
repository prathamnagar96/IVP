"""Exposure and Vulnerability layers calculation (Section 5.3).

Exposure counts elements inside the unit AND inside its modelled runout footprint.
E = norm(w_p * log(1 + pop) + w_b * log(1 + buildings) + w_c * critical + w_r * road_km)
"""

from typing import Dict, Any, List, Optional
import numpy as np


class ExposureCalculator:
    def __init__(
        self,
        weight_pop: float = 0.35,
        weight_buildings: float = 0.30,
        weight_critical: float = 0.25,
        weight_road_km: float = 0.10,
        max_reference_score: float = 10.0,
    ):
        self.w_p = weight_pop
        self.w_b = weight_buildings
        self.w_c = weight_critical
        self.w_r = weight_road_km
        self.max_ref = max_reference_score

    def compute_raw_score(
        self,
        population: float,
        building_count: int,
        critical_facilities: int,
        road_length_km: float,
    ) -> float:
        """Compute unnormalized weighted log-exposure sum."""
        pop_term = self.w_p * np.log1p(max(0.0, population))
        bldg_term = self.w_b * np.log1p(max(0, building_count))
        crit_term = self.w_c * max(0, critical_facilities)
        road_term = self.w_r * max(0.0, road_length_km)

        return float(pop_term + bldg_term + crit_term + road_term)

    def normalize_score(self, raw_score: float) -> float:
        """Normalise exposure score smoothly to [0.0, 1.0]."""
        norm = 1.0 - np.exp(-raw_score / (self.max_ref / 3.0))
        return float(np.clip(norm, 0.0, 1.0))

    def compute_unit_exposure(
        self,
        internal_elements: Dict[str, float],
        runout_elements: Optional[Dict[str, float]] = None,
        vulnerability_override: Optional[float] = None,
    ) -> Dict[str, float]:
        """Aggregate exposure elements inside the unit plus those inside the runout footprint."""
        pop = internal_elements.get("population", 0.0)
        bldg = internal_elements.get("buildings", 0.0)
        crit = internal_elements.get("critical_facilities", 0.0)
        road = internal_elements.get("road_km", 0.0)

        # Add elements in the modelled runout footprint
        if runout_elements:
            pop += runout_elements.get("population", 0.0)
            bldg += runout_elements.get("buildings", 0.0)
            crit += runout_elements.get("critical_facilities", 0.0)
            road += runout_elements.get("road_km", 0.0)

        raw = self.compute_raw_score(pop, int(bldg), int(crit), road)
        exposure_norm = self.normalize_score(raw)

        # Vulnerability factor: default 1.0 when unknown (conservative)
        vulnerability = vulnerability_override if vulnerability_override is not None else 1.0
        vulnerability = float(np.clip(vulnerability, 0.1, 1.0))

        return {
            "exposure": round(exposure_norm, 4),
            "vulnerability": round(vulnerability, 4),
            "raw_exposure": round(raw, 4),
            "total_population": pop,
            "total_buildings": bldg,
            "total_critical": crit,
            "total_road_km": road,
        }
