"""QueueItem builder, schema validation, and priority queue assembler (Section 5, 5.10)."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import jsonschema

from ..common.types import (
    QueueItem,
    Scores,
    DeformationInfo,
    RunoutInfo,
    DataStatus,
    Lane,
)


class QueueBuilder:
    def __init__(self, schema_path: Optional[Path] = None):
        if schema_path is None:
            # Look in contracts directory
            base_dir = Path(__file__).resolve().parents[3]
            schema_path = base_dir / "contracts" / "queue_item.schema.json"
            if not schema_path.exists():
                # Fallback to local package contracts
                schema_path = (
                    Path(__file__).resolve().parents[2]
                    / "contracts"
                    / "queue_item.schema.json"
                )

        self.schema = None
        if schema_path and Path(schema_path).exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)

    def validate_item_json(self, item_dict: Dict[str, Any]) -> bool:
        """Validate a serialized QueueItem against the official JSON schema."""
        if self.schema is None:
            return True
        jsonschema.validate(instance=item_dict, schema=self.schema)
        return True

    def build_queue_items(
        self,
        raw_unit_records: List[Dict[str, Any]],
        run_id: str,
        validate: bool = True,
    ) -> List[QueueItem]:
        """Convert processed unit records into validated QueueItems with priority ranks."""
        # Sort prioritised units by risk descending
        # Lanes ordered by priority: INSTRUMENT -> DRONE_BASELINE -> RESCREEN -> AUDIT -> NONE
        lane_order = {
            Lane.INSTRUMENT: 1,
            Lane.DRONE_BASELINE: 2,
            Lane.RESCREEN: 3,
            Lane.AUDIT: 4,
            Lane.NONE: 5,
        }

        def sort_key(u: Dict[str, Any]):
            lane_val = u["lane"]
            if isinstance(lane_val, str):
                lane_enum = Lane(lane_val)
            else:
                lane_enum = lane_val
            return (lane_order.get(lane_enum, 99), -u["risk"])

        sorted_units = sorted(raw_unit_records, key=sort_key)

        queue_items = []
        rank_counter = 1

        for u in sorted_units:
            lane_val = u["lane"]
            lane_enum = Lane(lane_val) if isinstance(lane_val, str) else lane_val

            rank = rank_counter if lane_enum != Lane.NONE else None
            if lane_enum != Lane.NONE:
                rank_counter += 1

            status_val = u["data_status"]
            status_enum = (
                DataStatus(status_val) if isinstance(status_val, str) else status_val
            )

            def_status = u["deformation"]["status"]
            def_status_enum = (
                DataStatus(def_status) if isinstance(def_status, str) else def_status
            )

            item = QueueItem(
                slope_unit_id=u["unit_id"],
                run_id=run_id,
                process=u.get("process", ["shallow_debris"]),
                scores=Scores(
                    susceptibility=round(float(u["scores"]["susceptibility"]), 4),
                    hazard=round(float(u["scores"]["hazard"]), 4),
                    exposure=round(float(u["scores"]["exposure"]), 4),
                    vulnerability=round(float(u["scores"]["vulnerability"]), 4),
                    risk=round(float(u["scores"]["risk"]), 4),
                    risk_interval=[
                        round(float(u["scores"]["risk_interval"][0]), 4),
                        round(float(u["scores"]["risk_interval"][1]), 4),
                    ],
                ),
                deformation=DeformationInfo(
                    status=def_status_enum,
                    coverage_pct=round(float(u["deformation"]["coverage_pct"]), 1),
                    v_downslope_mm_yr=round(
                        float(u["deformation"]["v_downslope_mm_yr"]), 1
                    ),
                    v_sigma_mm_yr=round(float(u["deformation"]["v_sigma_mm_yr"]), 1),
                    ada=bool(u["deformation"]["ada"]),
                ),
                data_status=status_enum,
                unknown_reasons=u.get("unknown_reasons", []),
                runout=RunoutInfo(
                    inherited_from=u.get("runout", {}).get("inherited_from", []),
                    footprint_id=u.get("runout", {}).get("footprint_id", None),
                ),
                lane=lane_enum,
                priority_rank=rank,
            )

            if validate:
                # Validate serialized dict matches schema
                self.validate_item_json(item.model_dump(mode="json"))

            queue_items.append(item)

        return queue_items
