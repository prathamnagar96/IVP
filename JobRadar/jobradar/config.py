"""Configuration management for JobRadar API.

Loads settings from environment variables and sources.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_settings_override: "Settings | None" = None


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


    # Database
    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_key: str = Field(default="", description="Supabase service role key")

    # API
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=1, description="Number of API workers")

    # Auth
    rapidapi_proxy_secret: str | None = Field(
        default=None, description="RapidAPI proxy secret for validation"
    )
    api_keys: str = Field(
        default="", description="Comma-separated list of valid API keys"
    )

    # Rate limiting
    rate_limit_requests: int = Field(
        default=100, description="Requests per window per key"
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds"
    )

    # Alerting
    alert_webhook_url: str | None = Field(
        default=None, description="Discord/Slack webhook URL for run summaries"
    )

    # Scraper
    scraper_headless: bool = Field(
        default=True, description="Run Playwright in headless mode"
    )
    scraper_timeout: int = Field(
        default=30000, description="Page load timeout in milliseconds"
    )
    scraper_user_agent: str = Field(
        default="JobRadar/1.0 (+https://jobradar.example.com/bot)",
        description="User-Agent for scraping",
    )

    # Sync
    ats_sync_interval_hours: int = Field(
        default=6, description="ATS sync interval in hours"
    )
    scrape_sync_interval_hours: int = Field(
        default=24, description="Scraper sync interval in hours"
    )
    expiry_days: int = Field(
        default=30, description="Days after last_seen to mark listing expired"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format: json or console")

    @property
    def api_key_list(self) -> list[str]:
        """Parse comma-separated API keys into a list."""
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]


class SourceConfig:
    """Configuration for a single data source."""

    def __init__(self, data: dict[str, Any]):
        self.company: str = data["company"]
        self.ats: str = data["ats"]
        self.token: str = data["token"]
        self.enabled: bool = data.get("enabled", True)
        self.scrape_selectors: dict[str, str] | None = data.get("scrape_selectors")
        self.tags: list[str] = data.get("tags", [])
        self.notes: str | None = data.get("notes")

    @property
    def source_id(self) -> str:
        """Generate source identifier."""
        return f"{self.ats}:{self.token}"


def load_sources(sources_path: Path | None = None) -> list[SourceConfig]:
    """Load source configurations from sources.yaml."""
    if sources_path is None:
        sources_path = Path(__file__).parent.parent / "sources.yaml"

    if not sources_path.exists():
        raise FileNotFoundError(f"Sources file not found: {sources_path}")

    with sources_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError("sources.yaml must contain a list of source objects")

    sources = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if not item.get("enabled", True):
            continue
        sources.append(SourceConfig(item))

    return sources


def get_settings() -> Settings:
    """Get cached settings instance."""
    global _settings_override
    if _settings_override is not None:
        return _settings_override
    return Settings()


def set_settings(settings: Settings | None = None) -> Settings | None:
    """Set an application-wide settings override for tests or app wiring."""
    global _settings_override
    _settings_override = settings
    return _settings_override