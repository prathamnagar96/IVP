"""Regional Advisory Matrix combining Susceptibility Class and Rain Class (Section 5.6).

Emits RegionalAdvisory candidate messages conforming to contracts/regional_advisory.schema.json.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from ..common.types import (
    SusceptibilityClass,
    RainClass,
    AdvisoryLevel,
    RegionalAdvisory,
    RainfallSummary,
)


# Matrix definition from Section 5.6
ADVISORY_MATRIX: Dict[str, Dict[str, AdvisoryLevel]] = {
    SusceptibilityClass.LOW.value: {
        RainClass.NORMAL.value: AdvisoryLevel.NONE,
        RainClass.WATCH.value: AdvisoryLevel.NONE,
        RainClass.EXCEEDED.value: AdvisoryLevel.ADVISORY,
        RainClass.EXTREME.value: AdvisoryLevel.ADVISORY,
    },
    SusceptibilityClass.MODERATE.value: {
        RainClass.NORMAL.value: AdvisoryLevel.NONE,
        RainClass.WATCH.value: AdvisoryLevel.ADVISORY,
        RainClass.EXCEEDED.value: AdvisoryLevel.ADVISORY,
        RainClass.EXTREME.value: AdvisoryLevel.WARNING_CANDIDATE,
    },
    SusceptibilityClass.HIGH.value: {
        RainClass.NORMAL.value: AdvisoryLevel.NONE,
        RainClass.WATCH.value: AdvisoryLevel.ADVISORY,
        RainClass.EXCEEDED.value: AdvisoryLevel.WARNING_CANDIDATE,
        RainClass.EXTREME.value: AdvisoryLevel.WARNING_CANDIDATE,
    },
    SusceptibilityClass.VERY_HIGH.value: {
        RainClass.NORMAL.value: AdvisoryLevel.NONE,
        RainClass.WATCH.value: AdvisoryLevel.ADVISORY,
        RainClass.EXCEEDED.value: AdvisoryLevel.WARNING_CANDIDATE,
        RainClass.EXTREME.value: AdvisoryLevel.WARNING_CANDIDATE,
    },
}


def categorize_susceptibility(s_score: float) -> SusceptibilityClass:
    """Categorize calibrated continuous susceptibility score into class."""
    if s_score < 0.30:
        return SusceptibilityClass.LOW
    elif s_score < 0.60:
        return SusceptibilityClass.MODERATE
    elif s_score < 0.80:
        return SusceptibilityClass.HIGH
    else:
        return SusceptibilityClass.VERY_HIGH


class AdvisoryMatrixEngine:
    def __init__(self, region_id: str = "R01"):
        self.region_id = region_id

    def evaluate_cell(
        self, s_class: SusceptibilityClass, r_class: RainClass
    ) -> AdvisoryLevel:
        """Lookup advisory level in the regional matrix."""
        s_val = s_class.value if hasattr(s_class, "value") else str(s_class)
        r_val = r_class.value if hasattr(r_class, "value") else str(r_class)
        return ADVISORY_MATRIX.get(s_val, {}).get(r_val, AdvisoryLevel.NONE)

    def generate_advisory_candidate(
        self,
        s_class: SusceptibilityClass,
        r_class: RainClass,
        rainfall_summary: Dict[str, float],
        affected_units_count: int = 0,
        now: Optional[datetime] = None,
    ) -> RegionalAdvisory:
        """Generate a validated RegionalAdvisory payload for Phase 3 review."""
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        level = self.evaluate_cell(s_class, r_class)
        matrix_cell = f"{s_class.value}_{r_class.value}"

        advisory_id = f"ADV-{now.strftime('%Y-%m-%d')}-{uuid.uuid4().hex[:8]}"

        recommended_actions = []
        if level == AdvisoryLevel.WARNING_CANDIDATE:
            recommended_actions = [
                "Initiate immediate geotechnical expert review (Phase 3 SLA < 15 min)",
                "Prepare civil authority notification package",
                "Activate continuous in-situ sensor polling at instrumented sites",
                "Dispatch drone event reconnaissance if safe and feasible",
            ]
        elif level == AdvisoryLevel.ADVISORY:
            recommended_actions = [
                "Issue internal regional geotechnical advisory bulletin",
                "Monitor rainfall radar and gauge trends closely",
                "Verify sensor health on instrumented slopes in affected zone",
            ]
        else:
            recommended_actions = ["Routine monitoring; nominal state"]

        advisory = RegionalAdvisory(
            advisory_id=advisory_id,
            region_id=self.region_id,
            created_at=now.isoformat(),
            level=level,
            matrix_cell=matrix_cell,
            susceptibility_class=s_class,
            rain_class=r_class,
            rainfall_summary=RainfallSummary(
                api_mm=rainfall_summary.get("api_mm", 0.0),
                max_intensity_mm_h=rainfall_summary.get("max_intensity_mm_h", 0.0),
                duration_h=rainfall_summary.get("duration_h", 1.0),
                id_exceedance_ratio=rainfall_summary.get("id_exceedance_ratio", 0.0),
            ),
            affected_units_count=affected_units_count,
            recommended_actions=recommended_actions,
        )

        return advisory
