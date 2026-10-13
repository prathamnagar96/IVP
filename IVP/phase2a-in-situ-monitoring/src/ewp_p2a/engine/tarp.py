"""Trigger-Action-Response Plan (TARP) rule evaluation engine (Section 7.1)."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..common.types import (
    ProposedLevel,
    BreachTrigger,
    IVMForecast,
    IVMStatus,
)
from .corroboration import CorroborationEngine


class TARPEngine:
    def __init__(self, tarp_config: Dict[str, Any]):
        self.cfg = tarp_config
        self.corroboration = CorroborationEngine()

    def evaluate_site_tarp(
        self,
        sensor_velocities: Dict[str, float],
        sensor_accelerations: Dict[str, float],
        piezo_head_increase_m: float,
        ivm_forecast: IVMForecast,
        rain_id_class: str,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Evaluate TARP levels for instrumented slope site.

        Precedence: CRITICAL -> WARNING -> ADVISORY -> NOMINAL.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        th_version = self.cfg.get("threshold_version", "th-2026-09-01")
        levels_cfg = self.cfg.get("levels", {})
        adv_cfg = levels_cfg.get("advisory", {})
        warn_cfg = levels_cfg.get("warning", {})
        crit_cfg = levels_cfg.get("critical", {})

        triggers: List[BreachTrigger] = []

        # 1. Critical Evaluation
        # Condition A: a valid IVM window is only critical when its upper bound
        # is within the configured critical horizon.
        tf_crit_h = crit_cfg.get("tf_crit_h", 48.0)
        ivm_critical = False
        if ivm_forecast.status == IVMStatus.VALID and ivm_forecast.tf_window_utc:
            try:
                start = datetime.fromisoformat(
                    ivm_forecast.tf_window_utc[0].replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(
                    ivm_forecast.tf_window_utc[1].replace("Z", "+00:00")
                )
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                ivm_critical = (end - current_time).total_seconds() <= tf_crit_h * 3600
            except (ValueError, IndexError):
                ivm_critical = False
        if ivm_critical:
            triggers.append(BreachTrigger(
                rule="ivm_imminent_failure_window",
                sensor_id="IVM-ENGINE",
                value=tf_crit_h,
                unit="hours",
                threshold_version=th_version,
            ))
            return {
                "proposed_level": ProposedLevel.CRITICAL,
                "triggers": triggers,
            }

        # Condition B: High velocity >= v_crit
        v_crit = crit_cfg.get("v_downslope_mm_day", 50.0)
        for s_id, v in sensor_velocities.items():
            if v >= v_crit:
                triggers.append(BreachTrigger(
                    rule="v_crit",
                    sensor_id=s_id,
                    value=v,
                    unit="mm/day",
                    threshold_version=th_version,
                ))
        if triggers:
            return {
                "proposed_level": ProposedLevel.CRITICAL,
                "triggers": triggers,
            }

        # 2. Warning Evaluation
        # Condition: v >= v_warn corroborated by >= 2 sensors AND (acceleration or piezo rise)
        v_warn = warn_cfg.get("v_downslope_mm_day", 10.0)
        warn_sensors = [s_id for s_id, v in sensor_velocities.items() if v >= v_warn]

        has_corroboration = self.corroboration.check_corroboration(
            warn_sensors, required_min_sensors=warn_cfg.get("corroboration_min_sensors", 2)
        )
        has_accel = any(a > 0 for a in sensor_accelerations.values())
        has_piezo_warn = piezo_head_increase_m >= warn_cfg.get("piezo_head_increase_m", 5.0)

        if has_corroboration and (has_accel or has_piezo_warn):
            for s_id in warn_sensors:
                triggers.append(BreachTrigger(
                    rule="v_warn",
                    sensor_id=s_id,
                    value=sensor_velocities[s_id],
                    unit="mm/day",
                    threshold_version=th_version,
                ))
            if has_piezo_warn:
                triggers.append(BreachTrigger(
                    rule="piezo_warn",
                    sensor_id="PZ-01",
                    value=piezo_head_increase_m,
                    unit="m_head",
                    threshold_version=th_version,
                ))
            return {
                "proposed_level": ProposedLevel.WARNING,
                "triggers": triggers,
            }

        # 3. Advisory Evaluation
        v_adv = adv_cfg.get("v_downslope_mm_day", 4.5)
        adv_sensors = [s_id for s_id, v in sensor_velocities.items() if v >= v_adv]
        rain_exceeded = (rain_id_class in ["EXCEEDED", "EXTREME"])

        if adv_sensors or rain_exceeded:
            for s_id in adv_sensors:
                triggers.append(BreachTrigger(
                    rule="v_advisory",
                    sensor_id=s_id,
                    value=sensor_velocities[s_id],
                    unit="mm/day",
                    threshold_version=th_version,
                ))
            if rain_exceeded:
                triggers.append(BreachTrigger(
                    rule="rain_id_advisory",
                    sensor_id="RAIN-01",
                    value=1.0,
                    unit="exceeded",
                    threshold_version=th_version,
                ))
            return {
                "proposed_level": ProposedLevel.ADVISORY,
                "triggers": triggers,
            }

        return {
            "proposed_level": None,
            "triggers": [],
        }
