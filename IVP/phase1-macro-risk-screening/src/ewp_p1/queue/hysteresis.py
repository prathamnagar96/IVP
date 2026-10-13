"""Queue hysteresis engine to prevent high-frequency lane oscillation (Section 5.10).

Requires lane promotions/demotions to persist for >= m cycles before transitioning,
unless bypassed by an acute event trigger (e.g., heavy rain, earthquake, or wildfire).
"""

from typing import Dict, List, Any
from ..common.types import Lane, DataStatus


class HysteresisManager:
    def __init__(self, persistence_cycles: int = 2):
        self.persistence_cycles = persistence_cycles
        # Stores historical lane proposals: unit_id -> list of recent lane proposals
        self.history: Dict[str, List[Lane]] = {}

    def apply_hysteresis(
        self,
        unit_id: str,
        current_lane: Lane,
        proposed_lane: Lane,
        event_trigger_active: bool = False,
    ) -> Lane:
        """Apply hysteresis smoothing across screening cycles.

        If event_trigger_active is True: lane change takes effect immediately without waiting.
        Otherwise: proposed lane must match for >= persistence_cycles consecutive cycles.
        """
        if event_trigger_active or proposed_lane == current_lane:
            self.history[unit_id] = [proposed_lane]
            return proposed_lane

        # Retrieve history
        past_proposals = self.history.get(unit_id, [current_lane])
        past_proposals.append(proposed_lane)
        if len(past_proposals) > self.persistence_cycles:
            past_proposals = past_proposals[-self.persistence_cycles:]
        self.history[unit_id] = past_proposals

        # Check if proposed lane has persisted for required cycles
        if len(past_proposals) >= self.persistence_cycles and all(
            p == proposed_lane for p in past_proposals
        ):
            return proposed_lane

        # Keep current lane until persistence condition is met
        return current_lane
