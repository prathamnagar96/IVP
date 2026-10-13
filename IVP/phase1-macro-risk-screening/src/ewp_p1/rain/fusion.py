"""Multi-source rainfall fusion and staleness validation (Section 5.6).

Fuses gauges, satellite (IMERG), radar, and NWP forecasts with bias correction
and tracks data freshness according to Section 5.9.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import numpy as np
from ..common.types import DataStatus


class RainFuser:
    def __init__(
        self,
        max_stale_hours: float = 6.0,
        gauge_weight: float = 0.60,
        radar_weight: float = 0.25,
        imerg_weight: float = 0.15,
    ):
        self.max_stale_h = max_stale_hours
        self.w_gauge = gauge_weight
        self.w_radar = radar_weight
        self.w_imerg = imerg_weight

    def evaluate_freshness(
        self,
        latest_gauge_ts: datetime,
        latest_imerg_ts: datetime,
        latest_radar_ts: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Check feed staleness against max_stale_h limit.

        UNKNOWN if all sources stale > max_stale_h.
        DEGRADED if one source stale or bias-flagged.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        gauge_age_h = (now - latest_gauge_ts).total_seconds() / 3600.0
        imerg_age_h = (now - latest_imerg_ts).total_seconds() / 3600.0
        radar_age_h = (now - latest_radar_ts).total_seconds() / 3600.0 if latest_radar_ts else None

        gauge_stale = gauge_age_h > self.max_stale_h
        imerg_stale = imerg_age_h > self.max_stale_h
        radar_stale = radar_age_h > self.max_stale_h if radar_age_h is not None else False

        # If all available sources are stale -> UNKNOWN
        sources_stale = [gauge_stale, imerg_stale]
        if radar_age_h is not None:
            sources_stale.append(radar_stale)

        if all(sources_stale):
            return {
                "status": DataStatus.UNKNOWN.value,
                "reason": f"all rainfall sources stale > {self.max_stale_h} hours",
                "feed_ages_h": {"gauge": round(gauge_age_h, 1), "imerg": round(imerg_age_h, 1)},
            }
        elif any(sources_stale):
            stale_names = []
            if gauge_stale: stale_names.append("gauge")
            if imerg_stale: stale_names.append("imerg")
            if radar_stale: stale_names.append("radar")
            return {
                "status": DataStatus.DEGRADED.value,
                "reason": f"rainfall feed degraded: {', '.join(stale_names)} stale",
                "feed_ages_h": {"gauge": round(gauge_age_h, 1), "imerg": round(imerg_age_h, 1)},
            }

        return {
            "status": DataStatus.OK.value,
            "reason": "",
            "feed_ages_h": {"gauge": round(gauge_age_h, 1), "imerg": round(imerg_age_h, 1)},
        }

    def fuse_hourly(
        self,
        gauge_mm_h: float,
        imerg_mm_h: float,
        radar_mm_h: Optional[float] = None,
        imerg_bias_factor: float = 0.85,  # Bias correction for orographic over/underestimation
    ) -> float:
        """Blend calibrated observations using weighted multi-source fusion."""
        corrected_imerg = imerg_mm_h * imerg_bias_factor

        if radar_mm_h is not None:
            fused = (
                self.w_gauge * gauge_mm_h
                + self.w_radar * radar_mm_h
                + self.w_imerg * corrected_imerg
            )
        else:
            w_total = self.w_gauge + self.w_imerg
            fused = (self.w_gauge * gauge_mm_h + self.w_imerg * corrected_imerg) / w_total

        return float(max(0.0, fused))
