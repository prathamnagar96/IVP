"""Conservative mission scheduling and go/no-go evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MissionState(str, Enum):
    QUEUED = "QUEUED"
    GO = "GO"
    NO_GO = "NO_GO"


@dataclass(frozen=True)
class WeatherLimits:
    wind_ms: float
    gust_ms: float
    visibility_m: float
    precipitation_allowed: bool = False


def evaluate_go_no_go(
    *,
    permit_valid: bool,
    crew_available: bool,
    batteries_available: bool,
    wind_ms: float,
    gust_ms: float,
    visibility_m: float,
    precipitation: bool,
    limits: WeatherLimits,
) -> dict[str, object]:
    """Return a safe dispatch decision; failed conditions keep the mission queued."""
    reasons: list[str] = []
    if not permit_valid:
        reasons.append("permit_invalid")
    if not crew_available:
        reasons.append("crew_unavailable")
    if not batteries_available:
        reasons.append("batteries_unavailable")
    if wind_ms > limits.wind_ms:
        reasons.append("wind_limit")
    if gust_ms > limits.gust_ms:
        reasons.append("gust_limit")
    if visibility_m < limits.visibility_m:
        reasons.append("visibility_limit")
    if precipitation and not limits.precipitation_allowed:
        reasons.append("precipitation")
    allowed = not reasons
    return {
        "state": MissionState.GO.value if allowed else MissionState.QUEUED.value,
        "go": allowed,
        "reasons": reasons,
    }
