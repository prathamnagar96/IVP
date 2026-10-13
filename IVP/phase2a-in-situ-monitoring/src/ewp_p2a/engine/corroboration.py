"""Corroboration (k-of-n voting) and persistence tracking for early-warning triggers (Section 7.1)."""

from typing import Dict, List, Set, Any
from datetime import datetime, timedelta, timezone


class CorroborationEngine:
    def __init__(self):
        # Persistence records: (site_id, rule_name) -> first_triggered_timestamp
        self.trigger_start_times: Dict[str, datetime] = {}

    def check_corroboration(
        self,
        active_sensor_ids: List[str],
        required_min_sensors: int = 2,
    ) -> bool:
        """Verify k-of-n voting: at least required_min_sensors independent sensors must confirm trigger."""
        unique_sensors = set(active_sensor_ids)
        return len(unique_sensors) >= required_min_sensors

    def check_persistence(
        self,
        trigger_key: str,
        is_active: bool,
        required_persist_hours: float,
        current_time: datetime,
    ) -> bool:
        """Verify that a trigger condition has persisted continuously for >= required_persist_hours."""
        if not is_active:
            # Reset persistence clock if condition clears
            self.trigger_start_times.pop(trigger_key, None)
            return False

        if trigger_key not in self.trigger_start_times:
            self.trigger_start_times[trigger_key] = current_time

        start_time = self.trigger_start_times[trigger_key]
        elapsed_hours = (current_time - start_time).total_seconds() / 3600.0

        return elapsed_hours >= required_persist_hours
