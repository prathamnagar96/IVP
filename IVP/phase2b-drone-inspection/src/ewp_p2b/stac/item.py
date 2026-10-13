"""Build and validate Phase 2B STAC DroneProduct items."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import jsonschema


def build_drone_product(
    *,
    site_id: str,
    observed_at: datetime,
    mission_type: str,
    assets: Mapping[str, str | Mapping[str, Any]],
    ground_density_ppm2: float,
    registration_rmse_m: float,
    lod95_m: float,
    qc_status: str,
    volume_change_m3: float | None = None,
    geometry: Mapping[str, Any] | None = None,
    bbox: list[float] | None = None,
    mission_id: str | None = None,
) -> dict[str, Any]:
    """Construct a contract-shaped STAC Item; callers may validate it explicitly."""
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    date = observed_at.astimezone(timezone.utc).date().isoformat()
    payload: dict[str, Any] = {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": f"{site_id}_{date}_{mission_type.lower()}",
        "properties": {
            "datetime": observed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mission_type": mission_type,
            "ground_density_ppm2": ground_density_ppm2,
            "reg_rmse_m": registration_rmse_m,
            "lod95_m": lod95_m,
            "qc_status": qc_status,
        },
        "assets": dict(assets),
    }
    if volume_change_m3 is not None:
        payload["properties"]["volume_change_m3"] = volume_change_m3
    if geometry is not None:
        payload["geometry"] = dict(geometry)
    if bbox is not None:
        payload["bbox"] = list(bbox)
    if mission_id is not None:
        payload["properties"]["mission_id"] = mission_id
    return payload


def validate_drone_product(item: Mapping[str, Any], schema_path: Path | None = None) -> None:
    """Validate a STAC item against the shared DroneProduct contract."""
    if schema_path is None:
        schema_path = Path(__file__).resolve().parents[4] / "contracts" / "drone_product.schema.json"
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    jsonschema.validate(dict(item), schema)
