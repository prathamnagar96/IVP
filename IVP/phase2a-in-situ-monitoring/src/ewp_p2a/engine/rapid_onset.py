"""Rapid-onset triggering engine for shallow slides and debris flows (Section 7.3).

Provides fast-lane threshold detection for sudden hydrological surges and channel geophones
without relying on tertiary creep IVM.
"""

from typing import Dict, Any, List, Optional
from ..common.types import ProposedLevel, BreachTrigger


class RapidOnsetEngine:
    def __init__(
        self,
        pore_pressure_rate_limit_kpa_h: float = 5.0,
        geophone_amplitude_mv_threshold: float = 250.0,
        stage_height_rise_rate_m_min: float = 0.3,
    ):
        self.pz_rate_limit = pore_pressure_rate_limit_kpa_h
        self.geophone_thresh = geophone_amplitude_mv_threshold
        self.stage_rate_limit = stage_height_rise_rate_m_min

    def evaluate_rapid_onset(
        self,
        rain_id_class: str,
        pore_pressure_rise_rate_kpa_h: float = 0.0,
        geophone_max_mv: float = 0.0,
        stage_rise_rate_m_min: float = 0.0,
        threshold_version: str = "th-rapid-v1",
    ) -> Dict[str, Any]:
        """Check for acute physical and hydrological rapid-onset breach triggers."""
        triggers = []
        proposed_level = None

        if geophone_max_mv >= self.geophone_thresh:
            triggers.append(BreachTrigger(
                rule="debris_flow_geophone_acoustic",
                sensor_id="GEO-01",
                value=geophone_max_mv,
                unit="mV",
                threshold_version=threshold_version,
            ))
            proposed_level = ProposedLevel.CRITICAL

        elif stage_rise_rate_m_min >= self.stage_rate_limit:
            triggers.append(BreachTrigger(
                rule="channel_stage_flash_rise",
                sensor_id="STAGE-01",
                value=stage_rise_rate_m_min,
                unit="m/min",
                threshold_version=threshold_version,
            ))
            proposed_level = ProposedLevel.CRITICAL

        elif pore_pressure_rise_rate_kpa_h >= self.pz_rate_limit:
            triggers.append(BreachTrigger(
                rule="hydro_pore_pressure_surge",
                sensor_id="PZ-01",
                value=pore_pressure_rise_rate_kpa_h,
                unit="kPa/h",
                threshold_version=threshold_version,
            ))
            proposed_level = ProposedLevel.WARNING if rain_id_class != "EXTREME" else ProposedLevel.CRITICAL

        elif rain_id_class == "EXTREME":
            triggers.append(BreachTrigger(
                rule="extreme_rainfall_cloudburst",
                sensor_id="RAIN-01",
                value=1.0,
                unit="class",
                threshold_version=threshold_version,
            ))
            proposed_level = ProposedLevel.WARNING

        return {
            "triggered": len(triggers) > 0,
            "proposed_level": proposed_level.value if proposed_level else None,
            "triggers": triggers,
            "fast_lane": True if proposed_level == ProposedLevel.CRITICAL else False,
        }
