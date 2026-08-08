"""Shared pipeline sync result model."""

from __future__ import annotations


class SyncResult:
    """Result of a sync run."""

    def __init__(self) -> None:
        self.sources_total = 0
        self.sources_succeeded = 0
        self.sources_failed = 0
        self.sources_disabled = 0
        self.jobs_added = 0
        self.jobs_updated = 0
        self.jobs_expired = 0
        self.failed_sources: list[tuple[str, str]] = []  # (source_id, error)
        self.disabled_sources: list[str] = []
