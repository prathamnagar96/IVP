"""InSAR quality assessment and coverage checks (Section 5.7, 5.9)."""

from typing import Dict, Any, List
from ..common.types import DataStatus


class InSARQualityAssessor:
    def __init__(
        self,
        min_scenes: int = 25,
        min_coverage_pct: float = 30.0,
        ok_coverage_pct: float = 60.0,
    ):
        self.min_scenes = min_scenes
        self.min_coverage_pct = min_coverage_pct
        self.ok_coverage_pct = ok_coverage_pct

    def assess_quality(
        self,
        scene_count_asc: int,
        scene_count_desc: int,
        coverage_pct: float,
        has_sensitivity: bool = True,
    ) -> Dict[str, Any]:
        """Determine InSAR DataStatus (OK, DEGRADED, UNKNOWN) and reason codes.

        UNKNOWN if:
            - coverage < min_coverage_pct (30%)
            - max scenes across geometries < min_scenes (25)
            - no sensitivity (low projection denominator across all geometries)

        DEGRADED if:
            - coverage between min_coverage_pct and ok_coverage_pct (30% - 60%)
            - only one geometry available (e.g. Ascending only or Descending only)
            - one geometry has < min_scenes

        OK if:
            - dual geometry available with >= min_scenes each
            - coverage >= ok_coverage_pct (60%)
        """
        reasons = []

        if not has_sensitivity:
            return {
                "status": DataStatus.UNKNOWN.value,
                "reason": "low InSAR sensitivity to slope direction",
            }

        max_scenes = max(scene_count_asc, scene_count_desc)
        min_scenes_both = min(scene_count_asc, scene_count_desc)

        if coverage_pct < self.min_coverage_pct:
            reasons.append(
                f"InSAR coverage {coverage_pct:.1f}% below minimum threshold {self.min_coverage_pct}%"
            )
        if max_scenes < self.min_scenes:
            reasons.append(
                f"insufficient InSAR scenes (max={max_scenes} < {self.min_scenes})"
            )

        if len(reasons) > 0:
            return {
                "status": DataStatus.UNKNOWN.value,
                "reason": "; ".join(reasons),
            }

        # Check DEGRADED conditions
        degraded_reasons = []
        if coverage_pct < self.ok_coverage_pct:
            degraded_reasons.append(
                f"InSAR coverage {coverage_pct:.1f}% is partial (between {self.min_coverage_pct}% and {self.ok_coverage_pct}%)"
            )
        if scene_count_asc == 0 or scene_count_desc == 0:
            single = "Ascending" if scene_count_asc > 0 else "Descending"
            degraded_reasons.append(f"single InSAR geometry only ({single})")
        elif min_scenes_both < self.min_scenes:
            degraded_reasons.append(
                f"secondary geometry has fewer than {self.min_scenes} scenes"
            )

        if len(degraded_reasons) > 0:
            return {
                "status": DataStatus.DEGRADED.value,
                "reason": "; ".join(degraded_reasons),
            }

        return {
            "status": DataStatus.OK.value,
            "reason": "",
        }
