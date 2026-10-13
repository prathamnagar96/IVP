"""Ingestion worker for field MQTT telemetry (Section 5.2, 5.3).

Validates schema, performs idempotent deduplication on (sensor_id, channel, ts),
and manages out-of-order late-arriving back-fill logs.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Set, Tuple
from datetime import datetime, timezone
import jsonschema

from ..common.types import TelemetryMessage


class IngestionWorker:
    def __init__(self, schema_path: Optional[Path] = None):
        if schema_path is None:
            base_dir = Path(__file__).resolve().parents[3]
            schema_path = base_dir / "contracts" / "telemetry_message.schema.json"
            if not schema_path.exists():
                schema_path = Path(__file__).resolve().parents[4] / "contracts" / "telemetry_message.schema.json"

        self.schema = None
        if schema_path and Path(schema_path).exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)

        # In-memory deduplication set for (sensor_id, channel, ts)
        self.seen_messages: Set[Tuple[str, str, str]] = set()
        self.ingested_readings: Dict[Tuple[str, str], list] = {}  # (sensor_id, channel) -> sorted readings
        self.last_seen_ts: Dict[str, datetime] = {}

    def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate JSON schema compliance of incoming MQTT payload."""
        if self.schema is not None:
            jsonschema.validate(instance=payload, schema=self.schema)
        return True

    def ingest_message(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming telemetry message idempotently.

        Returns:
            dict indicating whether message was processed, deduplicated, or identified as late backfill.
        """
        self.validate_payload(raw_payload)
        msg = TelemetryMessage(**raw_payload)

        key = (msg.sensor_id, msg.channel, msg.ts)

        # Idempotent deduplication check
        if key in self.seen_messages:
            return {
                "status": "DUPLICATE_IGNORED",
                "sensor_id": msg.sensor_id,
                "ts": msg.ts,
                "seq": msg.seq,
            }

        self.seen_messages.add(key)

        ts_dt = datetime.fromisoformat(msg.ts.replace("z", "+00:00").replace("Z", "+00:00"))
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)

        # Check for late backfill
        sensor_last_ts = self.last_seen_ts.get(msg.sensor_id)
        is_late_backfill = False
        if sensor_last_ts and ts_dt < sensor_last_ts:
            is_late_backfill = True
        else:
            self.last_seen_ts[msg.sensor_id] = ts_dt

        # Store in time series buffer
        buf_key = (msg.sensor_id, msg.channel)
        if buf_key not in self.ingested_readings:
            self.ingested_readings[buf_key] = []

        self.ingested_readings[buf_key].append({
            "ts": ts_dt,
            "values": msg.values,
            "sigma": msg.sigma or {},
            "battery_v": msg.battery_v,
            "quality": msg.quality,
            "seq": msg.seq,
        })
        # Keep time-sorted
        self.ingested_readings[buf_key].sort(key=lambda r: r["ts"])

        return {
            "status": "ACCEPTED",
            "sensor_id": msg.sensor_id,
            "channel": msg.channel,
            "ts": msg.ts,
            "is_late_backfill": is_late_backfill,
        }
