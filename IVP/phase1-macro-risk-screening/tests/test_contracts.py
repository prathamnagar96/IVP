"""Contract validation tests against JSON Schema specifications (Section 5, 9)."""

import json
from pathlib import Path
import pytest
import jsonschema
from ewp_p1.common.types import (
    QueueItem,
    Scores,
    DeformationInfo,
    RunoutInfo,
    DataStatus,
    Lane,
    RegionalAdvisory,
    SusceptibilityClass,
    RainClass,
    AdvisoryLevel,
    RainfallSummary,
)


def load_schema(name: str):
    root_contracts = Path(__file__).resolve().parents[2] / "contracts" / name
    if not root_contracts.exists():
        root_contracts = Path(__file__).resolve().parents[1] / "contracts" / name
    with open(root_contracts, "r", encoding="utf-8") as f:
        return json.load(f)


def test_queue_item_validates_against_contract():
    """Verify that QueueItem model serialization strictly matches queue_item.schema.json."""
    schema = load_schema("queue_item.schema.json")

    # Example matching root README Section 5
    item = QueueItem(
        slope_unit_id="SU-R01-000123",
        run_id="p1-2026-10-10T00:00Z",
        process=["shallow_debris", "deep_seated"],
        scores=Scores(
            susceptibility=0.71,
            hazard=0.78,
            exposure=0.64,
            vulnerability=0.8,
            risk=0.40,
            risk_interval=[0.31, 0.52],
        ),
        deformation=DeformationInfo(
            status=DataStatus.OK,
            coverage_pct=62.0,
            v_downslope_mm_yr=-38.4,
            v_sigma_mm_yr=4.1,
            ada=True,
        ),
        data_status=DataStatus.OK,
        unknown_reasons=[],
        runout=RunoutInfo(
            inherited_from=["SU-R01-000119"],
            footprint_id="RO-8812",
        ),
        lane=Lane.INSTRUMENT,
        priority_rank=4,
    )

    data = item.model_dump(mode="json")
    # Validate against JSON schema
    jsonschema.validate(instance=data, schema=schema)


def test_regional_advisory_validates_against_contract():
    """Verify that RegionalAdvisory model serialization matches regional_advisory.schema.json."""
    schema = load_schema("regional_advisory.schema.json")

    advisory = RegionalAdvisory(
        advisory_id="ADV-2026-10-13-abc12345",
        region_id="R01",
        created_at="2026-10-13T12:00:00Z",
        level=AdvisoryLevel.WARNING_CANDIDATE,
        matrix_cell="HIGH_EXCEEDED",
        susceptibility_class=SusceptibilityClass.HIGH,
        rain_class=RainClass.EXCEEDED,
        rainfall_summary=RainfallSummary(
            api_mm=165.4,
            max_intensity_mm_h=24.5,
            duration_h=6.0,
            id_exceedance_ratio=1.35,
        ),
        affected_units_count=42,
        recommended_actions=["Deploy field warning team", "Review geotechnical instruments"],
    )

    data = advisory.model_dump(mode="json")
    jsonschema.validate(instance=data, schema=schema)
