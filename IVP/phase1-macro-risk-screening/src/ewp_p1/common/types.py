"""Domain types, enums, and data schemas for Phase 1."""

from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DataStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class Lane(str, Enum):
    INSTRUMENT = "INSTRUMENT"
    DRONE_BASELINE = "DRONE_BASELINE"
    RESCREEN = "RESCREEN"
    AUDIT = "AUDIT"
    NONE = "NONE"


class ProcessClass(str, Enum):
    SHALLOW_DEBRIS = "shallow_debris"
    ROCKFALL = "rockfall"
    DEEP_SEATED = "deep_seated"
    DEBRIS_FLOW = "debris_flow"


class SusceptibilityClass(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class RainClass(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    EXCEEDED = "EXCEEDED"
    EXTREME = "EXTREME"


class AdvisoryLevel(str, Enum):
    NONE = "NONE"
    ADVISORY = "ADVISORY"
    WARNING_CANDIDATE = "WARNING_CANDIDATE"


class Scores(BaseModel):
    susceptibility: float = Field(..., ge=0.0, le=1.0)
    hazard: float = Field(..., ge=0.0, le=1.0)
    exposure: float = Field(..., ge=0.0, le=1.0)
    vulnerability: float = Field(..., ge=0.0, le=1.0)
    risk: float = Field(..., ge=0.0, le=1.0)
    risk_interval: List[float] = Field(...)


class DeformationInfo(BaseModel):
    status: DataStatus
    coverage_pct: float = Field(..., ge=0.0, le=100.0)
    v_downslope_mm_yr: float
    v_sigma_mm_yr: float = Field(..., ge=0.0)
    ada: bool


class RunoutInfo(BaseModel):
    inherited_from: List[str] = Field(default_factory=list)
    footprint_id: Optional[str] = None


class QueueItem(BaseModel):
    slope_unit_id: str
    run_id: str
    process: List[str]
    scores: Scores
    deformation: DeformationInfo
    data_status: DataStatus
    unknown_reasons: List[str] = Field(default_factory=list)
    runout: RunoutInfo
    lane: Lane
    priority_rank: Optional[int] = None

    model_config = ConfigDict(use_enum_values=True)


class RainfallSummary(BaseModel):
    api_mm: float
    max_intensity_mm_h: float
    duration_h: float
    id_exceedance_ratio: float


class RegionalAdvisory(BaseModel):
    advisory_id: str
    region_id: str
    created_at: str
    level: AdvisoryLevel
    matrix_cell: str
    susceptibility_class: SusceptibilityClass
    rain_class: RainClass
    rainfall_summary: RainfallSummary
    affected_units_count: int = 0
    recommended_actions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)
