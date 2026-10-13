"""UNKNOWN logic, composite data quality evaluation, and re-acquisition ladder (Section 5.9).

Invariants:
- I2: Missing or low-quality data => UNKNOWN, never 'safe'.
- Invariant property: data_status == UNKNOWN => lane != NONE.
"""

from typing import Dict, Any, List, Optional, Tuple
from ..common.types import DataStatus, Lane


REACQUISITION_LADDER = [
    {
        "step": 1,
        "name": "Secondary Geometry / Longer Stack",
        "description": "Acquire alternate Sentinel-1 orbit geometry (descending/ascending) or wait for stack expansion",
        "owner": "InSAR Processing Team",
        "sla_days": 14,
    },
    {
        "step": 2,
        "name": "L-band SAR Acquisition",
        "description": "Order L-band SAR (NISAR / ALOS-2) to penetrate dense vegetation canopy",
        "owner": "Satellite Mission Tasking",
        "sla_days": 30,
    },
    {
        "step": 3,
        "name": "Corner Reflectors / In-situ GNSS",
        "description": "Deploy passive corner reflectors or campaign GNSS on stable ridge points",
        "owner": "Field Geotechnical Team",
        "sla_days": 45,
    },
    {
        "step": 4,
        "name": "Drone LiDAR Baseline (Phase 2B)",
        "description": "Dispatch high-resolution UAV LiDAR mission to establish bare-earth DTM baseline",
        "owner": "Drone Operations Unit",
        "sla_days": 21,
    },
    {
        "step": 5,
        "name": "Geotechnical Field Reconnaissance",
        "description": "Expert engineering geologist field walkover to measure structural joint attitudes and scarp indicators",
        "owner": "Chief Geotechnical Engineer",
        "sla_days": 60,
    },
]


def resolve_worst_status(statuses: List[DataStatus]) -> DataStatus:
    """Evaluate composite data status: worst quality among critical features."""
    if DataStatus.UNKNOWN in statuses:
        return DataStatus.UNKNOWN
    elif DataStatus.DEGRADED in statuses:
        return DataStatus.DEGRADED
    return DataStatus.OK


class QualityEvaluator:
    def __init__(self, critical_features: Optional[List[str]] = None):
        self.critical_features = critical_features or [
            "deformation",
            "optical",
            "rainfall",
            "structure",
        ]

    def evaluate_unit_data_status(
        self,
        feature_qualities: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Assess overall unit data status and gather reason codes.

        feature_qualities format:
            {
                "deformation": {"status": "OK"|"DEGRADED"|"UNKNOWN", "reason": "..."},
                "optical": {"status": "...", "reason": "..."},
                ...
            }
        """
        statuses = []
        unknown_reasons = []

        for feat in self.critical_features:
            q_info = feature_qualities.get(feat, {"status": DataStatus.UNKNOWN.value, "reason": f"missing feature {feat}"})
            status_str = q_info.get("status", DataStatus.UNKNOWN.value)
            try:
                status_enum = DataStatus(status_str)
            except ValueError:
                status_enum = DataStatus.UNKNOWN

            statuses.append(status_enum)

            reason = q_info.get("reason", "")
            if status_enum in (DataStatus.UNKNOWN, DataStatus.DEGRADED) and reason:
                unknown_reasons.append(f"[{feat}] {reason}")

        overall_status = resolve_worst_status(statuses)

        # Recommend re-acquisition steps if UNKNOWN
        recommended_ladder = []
        if overall_status == DataStatus.UNKNOWN:
            # Check what failed
            def_status = feature_qualities.get("deformation", {}).get("status")
            if def_status == DataStatus.UNKNOWN.value:
                recommended_ladder.extend([REACQUISITION_LADDER[0], REACQUISITION_LADDER[1]])
            struct_status = feature_qualities.get("structure", {}).get("status")
            if struct_status == DataStatus.UNKNOWN.value:
                recommended_ladder.append(REACQUISITION_LADDER[4])
            if not recommended_ladder:
                recommended_ladder.append(REACQUISITION_LADDER[3])

        return {
            "data_status": overall_status.value,
            "unknown_reasons": unknown_reasons,
            "reacquisition_plan": recommended_ladder,
        }
