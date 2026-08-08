"""Base connector interface and data models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class ConnectorError(Exception):
    """Raised when a connector fails to fetch or parse data.

    This is the only exception connectors should raise - all other
    exceptions should be caught and wrapped in this.
    """

    def __init__(self, message: str, source: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.source = source
        self.details = details or {}


@dataclass(slots=True)
class RawJob:
    """Normalized job data from any source, ready for pipeline processing."""

    title: str
    company: str
    company_url: str | None
    location: str | None
    description: str
    salary_structured: tuple[int, int, str] | None  # (min, max, currency)
    salary_text: str | None
    apply_url: str
    posted_at: datetime | None
    source: str  # e.g., "ats:greenhouse", "ats:lever", "ats:ashby", "scrape:custom"

    def __post_init__(self):
        # Ensure required fields are present
        if not self.title or not self.title.strip():
            raise ValueError("RawJob title cannot be empty")
        if not self.company or not self.company.strip():
            raise ValueError("RawJob company cannot be empty")
        if not self.apply_url or not self.apply_url.strip():
            raise ValueError("RawJob apply_url cannot be empty")
        if not self.source or not self.source.strip():
            raise ValueError("RawJob source cannot be empty")


class Connector(ABC):
    """Abstract base class for all data source connectors.

    Each connector implements fetch() to retrieve jobs from a specific source.
    The pipeline orchestrator treats all connectors uniformly.
    """

    source_id: str  # e.g., "ats:greenhouse", "ats:lever", "ats:ashby", "scrape:custom"

    @abstractmethod
    def fetch(self, company: str, token: str) -> list[RawJob]:
        """Fetch jobs from the source.

        Args:
            company: Company display name (for RawJob.company field)
            token: ATS board token or scrape URL

        Returns:
            List of RawJob objects

        Raises:
            ConnectorError: On any failure (network, parsing, auth, etc.)
        """
        pass


def parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse ISO format datetime string."""
    if not value:
        return None
    try:
        # Handle various ISO formats
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, AttributeError):
        return None


def parse_epoch_ms(value: int | float | str | None) -> datetime | None:
    """Parse millisecond epoch timestamp."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value) / 1000.0)
    except (ValueError, TypeError, OSError):
        return None