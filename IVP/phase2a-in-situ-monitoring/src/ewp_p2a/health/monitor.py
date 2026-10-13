"""Sensor health and site monitoring status evaluator (Section 8).

Invariants:
- A blind site is NEVER treated as stable.
- If primary measurements fail, monitoring status escalates immediately to BLIND.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..common.types import SensorHealthStatus, MonitoringStatus


class SiteHealthMonitor:
    def __init__(
        self,
        heartbeat_timeout_sec: float = 300.0,  # 5 minutes
        battery_low_voltage_v: float = 11.8,
        battery_critical_voltage_v: float = 11.2,
    ):
        self.heartbeat_timeout_sec = heartbeat_timeout_sec
        self.battery_low = battery_low_voltage_v
        self.battery_crit = battery_critical_voltage_v

    def evaluate_sensor_health(
        self,
        last_seen_ts: datetime,
        battery_v: float,
        is_flatlined: bool = False,
        spike_rate_pct: float = 0.0,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Assess per-sensor operational health (HEALTHY, DEGRADED, FAILED)."""
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        age_sec = (now - last_seen_ts).total_seconds()
        if age_sec < 0:
            return {
                "status": SensorHealthStatus.DEGRADED,
                "reason": "telemetry timestamp is in the future",
                "age_sec": age_sec,
            }

        # FAILED conditions: heartbeat timed out, dead battery, or flatlined
        if age_sec > self.heartbeat_timeout_sec:
            return {
                "status": SensorHealthStatus.FAILED,
                "reason": f"heartbeat timed out (silence for {age_sec:.0f}s > {self.heartbeat_timeout_sec}s)",
                "age_sec": age_sec,
            }
        if battery_v < self.battery_crit:
            return {
                "status": SensorHealthStatus.FAILED,
                "reason": f"critical battery depletion ({battery_v:.2f}V < {self.battery_crit}V)",
                "age_sec": age_sec,
            }
        if is_flatlined:
            return {
                "status": SensorHealthStatus.FAILED,
                "reason": "sensor flatline detected (frozen values)",
                "age_sec": age_sec,
            }

        # DEGRADED conditions: low battery or high spike rate
        if battery_v < self.battery_low or spike_rate_pct > 15.0:
            reasons = []
            if battery_v < self.battery_low:
                reasons.append(f"low battery ({battery_v:.2f}V)")
            if spike_rate_pct > 15.0:
                reasons.append(f"elevated spike rate ({spike_rate_pct:.1f}%)")
            return {
                "status": SensorHealthStatus.DEGRADED,
                "reason": "; ".join(reasons),
                "age_sec": age_sec,
            }

        return {
            "status": SensorHealthStatus.HEALTHY,
            "reason": "nominal",
            "age_sec": age_sec,
        }

    def evaluate_site_monitoring_status(
        self,
        primary_sensor_statuses: Dict[str, SensorHealthStatus],
        corroborating_sensor_statuses: Dict[str, SensorHealthStatus],
    ) -> Dict[str, Any]:
        """Determine composite site monitoring status (NOMINAL, DEGRADED, BLIND).

        Rules (Section 8):
        - BLIND: Any primary measurement is FAILED (site is blind and NEVER treated as stable).
        - DEGRADED: A secondary sensor is FAILED or primary is DEGRADED.
        - NOMINAL: All primary and secondary measurements healthy.
        """
        failed_primaries = [s for s, st in primary_sensor_statuses.items() if st == SensorHealthStatus.FAILED]
        degraded_primaries = [s for s, st in primary_sensor_statuses.items() if st == SensorHealthStatus.DEGRADED]
        failed_secondaries = [s for s, st in corroborating_sensor_statuses.items() if st == SensorHealthStatus.FAILED]

        if len(failed_primaries) > 0:
            return {
                "status": MonitoringStatus.BLIND,
                "reason": f"primary sensor(s) lost: {', '.join(failed_primaries)}; site is BLIND",
                "is_stable": False,  # Blind is NEVER stable!
                "immediate_ops_escalation": True,
            }

        if len(degraded_primaries) > 0 or len(failed_secondaries) > 0:
            return {
                "status": MonitoringStatus.DEGRADED,
                "reason": f"degraded redundancy (primaries: {degraded_primaries}, secondaries: {failed_secondaries})",
                "is_stable": False,
                "immediate_ops_escalation": False,
            }

        return {
            "status": MonitoringStatus.NOMINAL,
            "reason": "all instruments healthy",
            "is_stable": True,
            "immediate_ops_escalation": False,
        }
