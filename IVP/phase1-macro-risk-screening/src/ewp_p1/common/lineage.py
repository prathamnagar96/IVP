"""Lineage, provenance, and reproducibility tracking for Phase 1 (Invariant I5)."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def generate_run_id(timestamp: Optional[datetime] = None) -> str:
    """Generate ISO-8601 compliant UTC run_id formatted as p1-YYYY-MM-DDTHH:MMZ."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    elif timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.strftime("p1-%Y-%m-%dT%H:%MZ")


def get_git_commit_hash() -> str:
    """Retrieve current git commit hash if available, else placeholder."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode("ascii").strip()
        return commit
    except Exception:
        return "development-snapshot"


def compute_hash(data: Any) -> str:
    """Compute deterministic SHA-256 hash of a serialisable object or bytes."""
    hasher = hashlib.sha256()
    if isinstance(data, (bytes, bytearray)):
        hasher.update(data)
    elif isinstance(data, str):
        hasher.update(data.encode("utf-8"))
    elif isinstance(data, (dict, list)):
        serialized = json.dumps(data, sort_keys=True, default=str)
        hasher.update(serialized.encode("utf-8"))
    else:
        hasher.update(str(data).encode("utf-8"))
    return hasher.hexdigest()


class LineageRecord:
    def __init__(
        self,
        run_id: Optional[str] = None,
        code_version: Optional[str] = None,
        input_hash: Optional[str] = None,
        config_snapshot: Optional[Dict[str, Any]] = None,
    ):
        self.run_id = run_id or generate_run_id()
        self.code_version = code_version or get_git_commit_hash()
        self.input_hash = input_hash or ""
        self.config_snapshot = config_snapshot or {}
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "code_version": self.code_version,
            "input_hash": self.input_hash,
            "config_snapshot": self.config_snapshot,
            "created_at": self.created_at,
        }
