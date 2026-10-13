"""Domain models, contracts, and enums for Phase 2A."""

from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field, ConfigDict


class QualityEnum(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    BAD = "BAD"


class ProposedLevel(str, Enum):
    ADVISORY = "ADVISORY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class MonitoringStatus(str, Enum):
    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    BLIND = "BLIND"


class SensorHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class IVMStatus(str, Enum):
    VALID = "VALID"
    NOT_ACCELERATING = "NOT_ACCELERATING"
    NO_CONVERGENCE = "NO_CONVERGENCE"
    BELOW_NOISE_FLOOR = "BELOW_NOISE_FLOOR"
    RAIN_PULSE = "RAIN_PULSE"


class IVMValidityGrade(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RainIDClass(str, Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    EXCEEDED = "EXCEEDED"
    EXTREME = "EXTREME"


class TelemetryMessage(BaseModel):
    ts: str
    site_id: str
    sensor_id: str
    channel: str
    values: Dict[str, float]
    sigma: Optional[Dict[str, float]] = None
    quality: QualityEnum = QualityEnum.OK
    battery_v: float
    temperature_c: Optional[float] = None
    seq: int

    model_config = ConfigDict(use_enum_values=True)


class BreachTrigger(BaseModel):
    rule: str
    sensor_id: str
    value: float
    unit: str
    threshold_version: str


class IVMForecast(BaseModel):
    status: IVMStatus
    tf_window_utc: Optional[List[str]] = None
    validity: Optional[IVMValidityGrade] = None
    flags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)


class RainContext(BaseModel):
    id_class: RainIDClass
    api_mm: float

    model_config = ConfigDict(use_enum_values=True)


class BreachEvent(BaseModel):
    event_id: str
    site_id: str
    created_at: str
    proposed_level: ProposedLevel
    triggers: List[BreachTrigger]
    ivm: IVMForecast
    rain_context: RainContext
    monitoring_status: MonitoringStatus
    evidence_url: str

    model_config = ConfigDict(use_enum_values=True)
