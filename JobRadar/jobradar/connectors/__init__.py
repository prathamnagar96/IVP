"""Connector factory and exports."""

from __future__ import annotations

from jobradar.config import SourceConfig
from jobradar.connectors.ashby import AshbyConnector
from jobradar.connectors.base import Connector, ConnectorError, RawJob
from jobradar.connectors.greenhouse import GreenhouseConnector
from jobradar.connectors.lever import LeverConnector
from jobradar.connectors.scraper import ScraperConnector


def create_connector(
    source_config: SourceConfig,
    http_client=None,
    headless: bool = True,
    scraper_timeout: int = 30000,
    user_agent: str = "JobRadar/1.0 (+https://jobradar.example.com/bot)",
) -> Connector:
    """Create appropriate connector for the source type."""
    ats = source_config.ats.lower()

    if ats == "greenhouse":
        return GreenhouseConnector(client=http_client)
    elif ats == "lever":
        return LeverConnector(client=http_client)
    elif ats == "ashby":
        return AshbyConnector(client=http_client)
    elif ats == "scrape":
        return ScraperConnector(
            source_config=source_config,
            http_client=http_client,
            headless=headless,
            scraper_timeout=scraper_timeout,
            user_agent=user_agent,
        )
    else:
        raise ValueError(f"Unknown ATS type: {ats}")


__all__ = [
    "Connector",
    "ConnectorError",
    "RawJob",
    "GreenhouseConnector",
    "LeverConnector",
    "AshbyConnector",
    "ScraperConnector",
    "create_connector",
]