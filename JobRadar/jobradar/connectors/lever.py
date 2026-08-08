"""Lever ATS connector.

Endpoint: GET https://api.lever.co/v0/postings/{token}?mode=json

⚠️ IMPORTANT: Lever uses 'text' for the job title field, NOT 'title'.
This is a common source of bugs when copying from Greenhouse connector.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from jobradar.connectors.base import Connector, ConnectorError, RawJob, parse_epoch_ms


class LeverConnector(Connector):
    """Connector for Lever job board API."""

    source_id = "ats:lever"
    BASE_URL = "https://api.lever.co/v0/postings"
    REQUEST_TIMEOUT = 30.0

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
        """Fetch jobs from Lever board."""
        url = f"{self.BASE_URL}/{token}"
        params = {"mode": "json"}  # Required to get JSON instead of HTML

        client = await self._get_client()

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise ConnectorError(
                f"Lever API returned {e.response.status_code}",
                source=self.source_id,
                details={"company": company, "token": token, "status": e.response.status_code},
            ) from e
        except httpx.RequestError as e:
            raise ConnectorError(
                f"Lever API request failed: {e}",
                source=self.source_id,
                details={"company": company, "token": token},
            ) from e
        except ValueError as e:
            raise ConnectorError(
                f"Lever API returned invalid JSON: {e}",
                source=self.source_id,
                details={"company": company, "token": token},
            ) from e

        # Lever returns a list directly, not wrapped in an object
        if not isinstance(data, list):
            raise ConnectorError(
                "Lever API response is not a list",
                source=self.source_id,
                details={"company": company, "token": token},
            )

        raw_jobs = []
        for job in data:
            try:
                raw_job = self._to_raw_job(job, company)
                raw_jobs.append(raw_job)
            except Exception as e:
                print(f"Warning: Failed to parse Lever job for {company}: {e}")
                continue

        return raw_jobs

    def _to_raw_job(self, raw: dict[str, Any], company: str) -> RawJob:
        """Convert Lever job dict to RawJob.

        ⚠️ NOTE: Lever's title field is 'text', NOT 'title'!
        """
        # Location from categories
        categories = raw.get("categories", {}) or {}
        location = categories.get("location")

        # Workplace type for remote/hybrid/onsite
        workplace_type = raw.get("workplaceType")
        if workplace_type and workplace_type != "unspecified":
            if location:
                location = f"{location} ({workplace_type})"
            else:
                location = workplace_type.capitalize()

        # Description - prefer plain text, fall back to HTML
        description = raw.get("descriptionPlain") or raw.get("description", "") or ""

        # Posted date - Lever uses milliseconds since epoch
        posted_at = parse_epoch_ms(raw.get("createdAt"))

        # Apply URL
        apply_url = raw.get("applyUrl") or raw.get("hostedUrl", "")

        # Salary - Lever provides structured salaryRange when available
        salary_structured = self._extract_lever_salary(raw.get("salaryRange"))
        salary_text = raw.get("salaryRangeDescriptionPlain")

        return RawJob(
            title=raw.get("text", "").strip(),  # NOT 'title' - this is 'text'!
            company=company,
            company_url=None,  # Not directly available
            location=location,
            description=description,
            salary_structured=salary_structured,
            salary_text=salary_text,
            apply_url=apply_url,
            posted_at=posted_at,
            source=self.source_id,
        )

    def _extract_lever_salary(
        self, salary_range: dict[str, Any] | None
    ) -> tuple[int, int, str] | None:
        """Extract structured salary from Lever's salaryRange object."""
        if not salary_range or not isinstance(salary_range, dict):
            return None

        currency = salary_range.get("currency", "USD")
        interval = salary_range.get("interval", "yearly")
        min_val = salary_range.get("min")
        max_val = salary_range.get("max")

        if min_val is None or max_val is None:
            return None

        try:
            min_salary = int(float(min_val))
            max_salary = int(float(max_val))

            # Convert to yearly if needed
            if interval == "monthly":
                min_salary *= 12
                max_salary *= 12
            elif interval == "hourly":
                min_salary *= 2080  # 40 hrs/week * 52 weeks
                max_salary *= 2080

            if min_salary > 0 and max_salary > 0 and min_salary <= max_salary:
                return (min_salary, max_salary, currency)
        except (ValueError, TypeError):
            pass

        return None