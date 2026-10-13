"""Test sensor health evaluation and blind site handling (Section 8).

Invariants:
- A blind site is NEVER treated as stable.
- Lost primary measurement escalates immediately to BLIND status.
"""

from datetime import datetime, timedelta, timezone
import pytest
from ewp_p2a.health.monitor import SiteHealthMonitor
from ewp_p2a.common.types import SensorHealthStatus, MonitoringStatus


def test_sensor_health_heartbeat_and_battery():
    """Verify sensor health transitions on telemetry timeouts and low voltages."""
    monitor = SiteHealthMonitor(heartbeat_timeout_sec=300.0)
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)

    # 1. Healthy sensor
    res_ok = monitor.evaluate_sensor_health(
        last_seen_ts=now - timedelta(seconds=60),
        battery_v=12.6,
        now=now,
    )
    assert res_ok["status"] == SensorHealthStatus.HEALTHY

    # 2. Heartbeat timed out (> 300s) -> FAILED
    res_stale = monitor.evaluate_sensor_health(
        last_seen_ts=now - timedelta(seconds=400),
        battery_v=12.6,
        now=now,
    )
    assert res_stale["status"] == SensorHealthStatus.FAILED
    assert "heartbeat timed out" in res_stale["reason"]

    # 3. Low battery (11.6V < 11.8V) -> DEGRADED
    res_low_bat = monitor.evaluate_sensor_health(
        last_seen_ts=now - timedelta(seconds=30),
        battery_v=11.6,
        now=now,
    )
    assert res_low_bat["status"] == SensorHealthStatus.DEGRADED

    # 4. Critically dead battery (10.9V < 11.2V) -> FAILED
    res_crit_bat = monitor.evaluate_sensor_health(
        last_seen_ts=now - timedelta(seconds=30),
        battery_v=10.9,
        now=now,
    )
    assert res_crit_bat["status"] == SensorHealthStatus.FAILED


def test_site_blind_status_invariant():
    """Invariant test: A blind site is NEVER treated as stable."""
    monitor = SiteHealthMonitor()

    # Primary sensor GNSS-02 is FAILED
    primary_statuses = {
        "GNSS-02": SensorHealthStatus.FAILED,
        "EXT-01": SensorHealthStatus.HEALTHY,
    }
    secondary_statuses = {
        "PZ-01": SensorHealthStatus.HEALTHY,
        "TILT-01": SensorHealthStatus.HEALTHY,
    }

    site_health = monitor.evaluate_site_monitoring_status(
        primary_sensor_statuses=primary_statuses,
        corroborating_sensor_statuses=secondary_statuses,
    )

    # Must escalate to BLIND
    assert site_health["status"] == MonitoringStatus.BLIND
    # Invariant: is_stable must be False!
    assert site_health["is_stable"] is False
    assert site_health["immediate_ops_escalation"] is True
