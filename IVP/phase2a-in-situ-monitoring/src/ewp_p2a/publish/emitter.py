"""BreachEvent generator and evidence package emitter (Section 7.4, 7.5)."""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
import json
import jsonschema

from ..common.types import (
    BreachEvent,
    ProposedLevel,
    BreachTrigger,
    IVMForecast,
    RainContext,
    MonitoringStatus,
)


class BreachEmitter:
    def __init__(self, schema_path: Optional[Path] = None):
        if schema_path is None:
            base_dir = Path(__file__).resolve().parents[3]
            schema_path = base_dir / "contracts" / "breach_event.schema.json"
            if not schema_path.exists():
                schema_path = Path(__file__).resolve().parents[4] / "contracts" / "breach_event.schema.json"

        self.schema = None
        if schema_path and Path(schema_path).exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)

        # Active episode tracking: site_id -> persistent event_id
        self.active_episodes: Dict[str, str] = {}

    def build_breach_event(
        self,
        site_id: str,
        proposed_level: ProposedLevel,
        triggers: List[BreachTrigger],
        ivm_forecast: IVMForecast,
        rain_context: RainContext,
        monitoring_status: MonitoringStatus,
        evidence_url: Optional[str] = None,
        now: Optional[datetime] = None,
        validate: bool = True,
    ) -> BreachEvent:
        """Create an idempotent BreachEvent for Phase 3 review."""
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Retain identical event_id while site episode is elevated
        if site_id not in self.active_episodes:
            self.active_episodes[site_id] = str(uuid.uuid4())
        event_id = self.active_episodes[site_id]

        url = evidence_url or f"https://landslide-ewp.org/sites/{site_id}/evidence/{event_id}"

        event = BreachEvent(
            event_id=event_id,
            site_id=site_id,
            created_at=now.isoformat(),
            proposed_level=proposed_level,
            triggers=triggers,
            ivm=ivm_forecast,
            rain_context=rain_context,
            monitoring_status=monitoring_status,
            evidence_url=url,
        )

        if validate and self.schema is not None:
            payload = event.model_dump(mode="json")
            jsonschema.validate(instance=payload, schema=self.schema)

        return event

    def clear_episode(self, site_id: str):
        """Clear active episode upon confirmed de-escalation."""
        self.active_episodes.pop(site_id, None)
