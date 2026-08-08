"""Ashby ATS connector.

Endpoint: GET https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true

Ashby returns the entire board in a single response (no pagination).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from jobradar.connectors.base import Connector, ConnectorError, RawJob, parse_iso_datetime


class AshbyConnector(Connector):
    """Connector for Ashby job board API."""

    source_id = "ats:ashby"
    BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"
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
        """Fetch jobs from Ashby board."""
        url = f"{self.BASE_URL}/{token}"
        params = {"includeCompensation": "true"}

        client = await self._get_client()

        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise ConnectorError(
                f"Ashby API returned {e.response.status_code}",
                source=self.source_id,
                details={"company": company, "token": token, "status": e.response.status_code},
            ) from e
        except httpx.RequestError as e:
            raise ConnectorError(
                f"Ashby API request failed: {e}",
                source=self.source_id,
                details={"company": company, "token": token},
            ) from e
        except ValueError as e:
            raise ConnectorError(
                f"Ashby API returned invalid JSON: {e}",
                source=self.source_id,
                details={"company": company, "token": token},
            ) from e

        # Ashby response structure: { "jobs": [...], "apiVersion": "..." }
        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            raise ConnectorError(
                "Ashby API response 'jobs' is not a list",
                source=self.source_id,
                details={"company": company, "token": token},
            )

        raw_jobs = []
        for job in jobs:
            # Filter out unlisted/draft jobs
            if not job.get("isListed", True):
                continue

            try:
                raw_job = self._to_raw_job(job, company)
                raw_jobs.append(raw_job)
            except Exception as e:
                print(f"Warning: Failed to parse Ashby job for {company}: {e}")
                continue

        return raw_jobs

    def _to_raw_job(self, raw: dict[str, Any], company: str) -> RawJob:
        """Convert Ashby job dict to RawJob."""
        # Location - Ashby provides plain string location
        location = raw.get("location")

        # Add workplace type context
        workplace_type = raw.get("workplaceType")
        is_remote = raw.get("isRemote", False)
        if workplace_type and workplace_type != "unspecified":
            if location:
                location = f"{location} ({workplace_type})"
            else:
                location = workplace_type.capitalize()
        elif is_remote and location:
            location = f"{location} (Remote)"

        # Description - HTML format
        description = raw.get("descriptionHtml", "") or ""

        # Posted date
        posted_at = parse_iso_datetime(raw.get("publishedAt")) or parse_iso_datetime(
            raw.get("createdAt")
        )

        # Apply URL - Ashby uses 'applyUrl'
        apply_url = raw.get("applyUrl", "")

        # Salary - Ashby provides structured compensation when includeCompensation=true
        salary_structured = self._extract_ashby_compensation(raw.get("compensation"))
        salary_text = None  # Ashby doesn't provide narrative salary text separately

        return RawJob(
            title=raw.get("title", "").strip(),
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

    def _extract_ashby_compensation(
        self, compensation: dict[str, Any] | None
    ) -> tuple[int, int, str] | None:
        """Extract structured compensation from Ashby's compensation object."""
        if not compensation or not isinstance(compensation, dict):
            return None

        # Ashby compensation structure per their docs
        # Can have: currency, payPeriod, minAmount, maxAmount, etc.
        currency = compensation.get("currency", "USD")
        pay_period = compensation.get("payPeriod", "YEARLY")
        min_amount = compensation.get("minAmount")
        max_amount = compensation.get("maxAmount")

        if min_amount is None or max_amount is None:
            return None

        try:
            min_salary = int(float(min_amount))
            max_salary = int(float(max_amount))

            # Convert to yearly if needed
            if pay_period == "MONTHLY":
                min_salary *= 12
                max_salary *= 12
            elif pay_period == "HOURLY":
                min_salary *= 2080
                max_salary *= 2080
            elif pay_period == "WEEKLY":
                min_salary *= 52
                max_salary *= 52

            if min_salary > 0 and max_salary > 0 and min_salary <= max_salary:
                return (min_salary, max_salary, currency)
        except (ValueError, TypeError):
            pass

        return None