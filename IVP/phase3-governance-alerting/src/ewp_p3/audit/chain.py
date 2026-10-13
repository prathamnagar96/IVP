"""Append-only SHA-256 hash chain for workflow and delivery audit records."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class AuditRecord:
    sequence: int
    at: str
    actor: str
    action: str
    payload: dict[str, Any]
    previous_hash: str
    record_hash: str


class AuditChain:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def append(self, actor: str, action: str, payload: dict[str, Any]) -> AuditRecord:
        previous = self.records[-1].record_hash if self.records else "0" * 64
        sequence = len(self.records) + 1
        at = datetime.now(timezone.utc).isoformat()
        body = {
            "sequence": sequence, "at": at, "actor": actor, "action": action,
            "payload": payload, "previous_hash": previous,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        record = AuditRecord(**body, record_hash=digest)
        self.records.append(record)
        return record

    def verify(self) -> bool:
        previous = "0" * 64
        for expected_sequence, record in enumerate(self.records, start=1):
            if record.sequence != expected_sequence or record.previous_hash != previous:
                return False
            body = asdict(record)
            digest = body.pop("record_hash")
            actual = hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if digest != actual:
                return False
            previous = digest
        return True
