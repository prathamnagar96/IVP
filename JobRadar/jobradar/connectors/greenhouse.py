"""Greenhouse ATS connector.

Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx

from jobradar.connectors.base import Connector, ConnectorError, RawJob, parse_iso_datetime


class GreenhouseConnector(Connector):
    """Connector for Greenhouse job board API."""

    source_id = "ats:greenhouse"
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
    REQUEST_TIMEOUT = 30.0
    RATE_LIMIT_DELAY = 1.0  # seconds between requests

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.REQUEST_TIMEOUT),
                headers={"User-Agent": "JobRadar/1.0 (+https://jobradar.example.com/bot)"},
            )
        return self._client

    async def close(self):
        if self._owns_client and self._client:
            await self._client.aclose()
            self._client = None

    async def fetch(self, company: str, token: str) -> list[RawJob]:
        """Fetch jobs from Greenhouse board."""
        url = f"{self.BASE_URL}/{token}/jobs"
        params = {"content": "true"}  # Include HTML description

        client = await self._get_client()

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise ConnectorError(
                f"Greenhouse API returned {e.response.status_code}",
                source=self.source_id,
                details={"company": company, "token": token, "status": e.response.status_code},
            ) from e
        except httpx.RequestError as e:
            raise ConnectorError(
                f"Greenhouse API request failed: {e}",
                source=self.source_id,
                details={"company": company, "token": token},
            ) from e
        except ValueError as e:
            raise ConnectorError(
                f"Greenhouse API returned invalid JSON: {e}",
                source=self.source_id,
                details={"company": company, "token": token},
            ) from e

        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            raise ConnectorError(
                "Greenhouse API response 'jobs' is not a list",
                source=self.source_id,
                details={"company": company, "token": token},
            )

        raw_jobs = []
        for job in jobs:
            try:
                raw_job = self._to_raw_job(job, company)
                raw_jobs.append(raw_job)
            except Exception as e:
                # Log but continue - don't let one bad job break the whole batch
                # In production, you'd use structured logging here
                print(f"Warning: Failed to parse Greenhouse job for {company}: {e}")
                continue

        return raw_jobs

    def _to_raw_job(self, raw: dict[str, Any], company: str) -> RawJob:
        """Convert Greenhouse job dict to RawJob."""
        # Location: check metadata for detailed location first
        location = raw.get("location", {}).get("name")
        if not location or location.lower() in ("remote", "hybrid", "on-site", "onsite"):
            # Check metadata for more specific location
            for meta in raw.get("metadata", []):
                if isinstance(meta, dict):
                    name = meta.get("name", "").lower()
                    if "location" in name or "city" in name or "country" in name:
                        value = meta.get("value")
                        if value and isinstance(value, str):
                            location = value
                            break

        # Description from content (HTML)
        description = raw.get("content", "") or ""

        # Posted/updated date
        posted_at = parse_iso_datetime(raw.get("updated_at"))

        # Apply URL
        apply_url = raw.get("absolute_url", "")

        # Greenhouse doesn't provide structured salary
        # Salary might be in description HTML - we'll use regex fallback in pipeline
        salary_text = description if description else None

        return RawJob(
            title=raw.get("title", "").strip(),
            company=company,
            company_url=None,  # Not directly available from Greenhouse board API
            location=location,
            description=description,
            salary_structured=None,
            salary_text=salary_text,
            apply_url=apply_url,
            posted_at=posted_at,
            source=self.source_id,
        )


def extract_salary_from_text(text: str) -> tuple[int, int, str] | None:
    """Extract salary range from text using regex patterns.

    Returns (min_salary, max_salary, currency) or None if not found.
    """
    if not text:
        return None

    # Common patterns: $120k-$150k, $120,000-$150,000, 120k-150k, up to $150k
    patterns = [
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?\s*[-–—]\s*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?",
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[-–—]\s*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?",
        r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]\s*[-–—]\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]",
        r"up to\s+\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?",
        r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?\s*(?:to|-)\s*\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                min_val = _parse_salary_value(groups[0])
                max_val = _parse_salary_value(groups[1])
                if min_val and max_val and min_val <= max_val:
                    return (min_val, max_val, "USD")
            elif len(groups) == 1:
                # "up to" pattern
                max_val = _parse_salary_value(groups[0])
                if max_val:
                    return (max_val // 2, max_val, "USD")  # Rough estimate

    return None


def _parse_salary_value(value: str) -> int | None:
    """Parse salary string to integer (annual USD)."""
    try:
        # Remove commas
        clean = value.replace(",", "")
        num = float(clean)
        # If value looks like it's in thousands (e.g., 120, 150)
        if num < 1000:
            num *= 1000
        return int(num)
    except (ValueError, TypeError):
        return None