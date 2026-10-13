"""Priority lane determination engine (Section 5.10).

Invariants:
- UNKNOWN never lowers rank or classifies as safe.
- Invariant property: data_status == UNKNOWN => lane != NONE.
"""

from typing import Dict, Any, List
from ..common.types import Lane, DataStatus


class LaneAssigner:
    def __init__(
        self,
        e_min: float = 0.30,
        s_high: float = 0.70,
        s_med: float = 0.40,
        e_med: float = 0.30,
        r_drone: float = 0.15,
    ):
        self.e_min = e_min
        self.s_high = s_high
        self.s_med = s_med
        self.e_med = e_med
        self.r_drone = r_drone

    def evaluate_initial_lane(
        self,
        risk: float,
        susceptibility: float,
        exposure: float,
        has_ada: bool,
        data_status: DataStatus,
    ) -> Lane:
        """Assign preliminary lane according to rule precedence:

        1. INSTRUMENT eligibility: E >= e_min and (ADA or S >= s_high).
        2. DRONE_BASELINE: R >= r_drone or ADA present.
        3. RESCREEN: UNKNOWN data status.
        4. NONE: (eligible for AUDIT random sampling).
        """
        is_unknown = (data_status == DataStatus.UNKNOWN)

        # UNKNOWN handling (Section 5.9): High S or High E with UNKNOWN data => lane RESCREEN
        if is_unknown:
            return Lane.RESCREEN

        # Instrument candidate check (known/observed critical slopes)
        if exposure >= self.e_min and (has_ada or susceptibility >= self.s_high):
            return Lane.INSTRUMENT

        # Drone baseline check
        if risk >= self.r_drone or has_ada:
            return Lane.DRONE_BASELINE

        return Lane.NONE
