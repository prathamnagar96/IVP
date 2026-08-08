"""Webhook alerting for run summaries."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from jobradar.config import Settings
from jobradar.pipeline.sync_result import SyncResult

logger = logging.getLogger(__name__)


async def send_run_summary(
    settings: Settings,
    result: SyncResult,
    run_started: datetime,
) -> None:
    """Send run summary to configured webhook."""
    if not settings.alert_webhook_url:
        return

    # Format summary message
    message = _format_summary(settings, result, run_started)

    payload = {"content": message}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.alert_webhook_url, json=payload)
            response.raise_for_status()
    except Exception as e:
        logger.warning(f"Failed to send webhook alert: {e}")


def _format_summary(
    settings: Settings,
    result: SyncResult,
    run_started: datetime,
) -> str:
    """Format run summary for Discord/Slack."""
    timestamp = run_started.strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"JobRadar sync — {timestamp}",
        f"✅ {result.sources_succeeded} sources synced · "
        f"{result.jobs_added} new / {result.jobs_updated} updated / "
        f"{result.jobs_expired} expired",
    ]

    if result.sources_failed > 0:
        failed_names = [src for src, _ in result.failed_sources]
        lines.append(f"⚠️ {result.sources_failed} sources failed: {', '.join(failed_names)}")

    if result.sources_disabled > 0:
        lines.append(f"🛑 {result.sources_disabled} sources disabled: {', '.join(result.disabled_sources)}")

    return "\n".join(lines)


async def send_test_alert(settings: Settings, message: str = "JobRadar test alert") -> bool:
    """Send a test alert to verify webhook configuration."""
    if not settings.alert_webhook_url:
        return False

    payload = {"content": message}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.alert_webhook_url, json=payload)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Test alert failed: {e}")
        return False