"""Capacity enforcement and lane quota manager (Section 5.10, capacity.yaml)."""

from typing import List, Dict, Any, Optional
from ..common.types import Lane, DataStatus


class CapacityManager:
    def __init__(self, quotas: Optional[Dict[str, int]] = None):
        # Default limits matching capacity.yaml
        self.quotas = quotas or {
            "INSTRUMENT": 20,
            "DRONE_BASELINE": 50,
            "RESCREEN": 100,
            "AUDIT": 100,
        }

    def enforce_quotas(
        self, candidate_units: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Sort candidates by risk and enforce lane quotas.

        Preserves Invariant: data_status == UNKNOWN => lane != NONE.
        """
        # Sort all candidates by risk descending
        sorted_units = sorted(candidate_units, key=lambda x: x["risk"], reverse=True)

        instrument_limit = self.quotas.get("INSTRUMENT", 20)
        drone_limit = self.quotas.get("DRONE_BASELINE", 50)
        rescreen_limit = self.quotas.get("RESCREEN", 100)

        assigned_units = []
        counts = {Lane.INSTRUMENT: 0, Lane.DRONE_BASELINE: 0, Lane.RESCREEN: 0, Lane.NONE: 0}

        for u in sorted_units:
            lane = u["lane"]
            status = u["data_status"]
            is_unknown = (status == DataStatus.UNKNOWN or status == DataStatus.UNKNOWN.value)

            if lane == Lane.INSTRUMENT:
                if counts[Lane.INSTRUMENT] < instrument_limit:
                    counts[Lane.INSTRUMENT] += 1
                    u["lane"] = Lane.INSTRUMENT
                elif counts[Lane.DRONE_BASELINE] < drone_limit:
                    # Spillover into drone baseline
                    counts[Lane.DRONE_BASELINE] += 1
                    u["lane"] = Lane.DRONE_BASELINE
                elif is_unknown and counts[Lane.RESCREEN] < rescreen_limit:
                    counts[Lane.RESCREEN] += 1
                    u["lane"] = Lane.RESCREEN
                else:
                    # Invariant preservation: UNKNOWN can never be NONE
                    if is_unknown:
                        u["lane"] = Lane.RESCREEN
                    else:
                        u["lane"] = Lane.NONE

            elif lane == Lane.DRONE_BASELINE:
                if counts[Lane.DRONE_BASELINE] < drone_limit:
                    counts[Lane.DRONE_BASELINE] += 1
                    u["lane"] = Lane.DRONE_BASELINE
                elif is_unknown and counts[Lane.RESCREEN] < rescreen_limit:
                    counts[Lane.RESCREEN] += 1
                    u["lane"] = Lane.RESCREEN
                else:
                    if is_unknown:
                        u["lane"] = Lane.RESCREEN
                    else:
                        u["lane"] = Lane.NONE

            elif lane == Lane.RESCREEN or is_unknown:
                counts[Lane.RESCREEN] += 1
                u["lane"] = Lane.RESCREEN

            else:
                u["lane"] = Lane.NONE

            assigned_units.append(u)

        return assigned_units
