"""Tests for ATS connectors using fixture data."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobradar.connectors.ashby import AshbyConnector
from jobradar.connectors.greenhouse import GreenhouseConnector
from jobradar.connectors.lever import LeverConnector


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


class TestGreenhouseConnector:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        fixture = load_fixture("greenhouse_jobs")
        if not fixture:
            pytest.skip("No greenhouse fixture found")

        connector = GreenhouseConnector()
        connector._client = AsyncMock()
        connector._client.get = AsyncMock()
        connector._client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: fixture,
            raise_for_status=lambda: None,
        )

        jobs = await connector.fetch("Test Company", "test-token")

        assert len(jobs) > 0
        for job in jobs:
            assert job.title
            assert job.company == "Test Company"
            assert job.apply_url
            assert job.source == "ats:greenhouse"

        await connector.close()

    @pytest.mark.asyncio
    async def test_fetch_http_error(self):
        connector = GreenhouseConnector()
        connector._client = AsyncMock()
        connector._client.get = AsyncMock()
        connector._client.get.side_effect = Exception("Network error")

        with pytest.raises(Exception):
            await connector.fetch("Test Company", "test-token")

        await connector.close()


class TestLeverConnector:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        fixture = load_fixture("lever_jobs")
        if not fixture:
            pytest.skip("No lever fixture found")

        connector = LeverConnector()
        connector._client = AsyncMock()
        connector._client.get = AsyncMock()
        connector._client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: fixture,
            raise_for_status=lambda: None,
        )

        jobs = await connector.fetch("Test Company", "test-token")

        assert len(jobs) > 0
        for job in jobs:
            assert job.title and job.title.strip()  # Lever uses 'text' field
            assert job.company == "Test Company"
            assert job.apply_url
            assert job.source == "ats:lever"

        await connector.close()

    @pytest.mark.asyncio
    async def test_title_field_is_text_not_title(self):
        """Verify Lever connector uses 'text' field for title, not 'title'."""
        fixture = {
            "id": "123",
            "text": "Software Engineer",  # Lever uses 'text'
            "title": "Wrong Title",  # This field shouldn't be used
            "hostedUrl": "https://lever.co/test",
            "applyUrl": "https://lever.co/test/apply",
            "categories": {"location": "Remote"},
            "descriptionPlain": "Description",
            "createdAt": 1700000000000,
        }

        connector = LeverConnector()
        connector._client = AsyncMock()
        connector._client.get = AsyncMock()
        connector._client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [fixture],
            raise_for_status=lambda: None,
        )

        jobs = await connector.fetch("Test Company", "test-token")

        assert len(jobs) == 1
        assert jobs[0].title == "Software Engineer"  # Not "Wrong Title"

        await connector.close()


class TestAshbyConnector:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        fixture = load_fixture("ashby_jobs")
        if not fixture:
            pytest.skip("No ashby fixture found")

        connector = AshbyConnector()
        connector._client = AsyncMock()
        connector._client.get = AsyncMock()
        connector._client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: fixture,
            raise_for_status=lambda: None,
        )

        jobs = await connector.fetch("Test Company", "test-token")

        assert len(jobs) > 0
        for job in jobs:
            assert job.title
            assert job.company == "Test Company"
            assert job.apply_url
            assert job.source == "ats:ashby"

        await connector.close()

    @pytest.mark.asyncio
    async def test_filters_unlisted_jobs(self):
        fixture = {
            "jobs": [
                {"title": "Listed Job", "isListed": True, "applyUrl": "https://test.com/1"},
                {"title": "Unlisted Job", "isListed": False, "applyUrl": "https://test.com/2"},
            ]
        }

        connector = AshbyConnector()
        connector._client = AsyncMock()
        connector._client.get = AsyncMock()
        connector._client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: fixture,
            raise_for_status=lambda: None,
        )

        jobs = await connector.fetch("Test Company", "test-token")

        assert len(jobs) == 1
        assert jobs[0].title == "Listed Job"

        await connector.close()

    @pytest.mark.asyncio
    async def test_compensation_parsing(self):
        fixture = {
            "jobs": [
                {
                    "title": "Engineer",
                    "isListed": True,
                    "applyUrl": "https://test.com/1",
                    "compensation": {
                        "currency": "USD",
                        "payPeriod": "YEARLY",
                        "minAmount": 120000,
                        "maxAmount": 150000,
                    },
                }
            ]
        }

        connector = AshbyConnector()
        connector._client = AsyncMock()
        connector._client.get = AsyncMock()
        connector._client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: fixture,
            raise_for_status=lambda: None,
        )

        jobs = await connector.fetch("Test Company", "test-token")

        assert len(jobs) == 1
        assert jobs[0].salary_structured == (120000, 150000, "USD")

        await connector.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])