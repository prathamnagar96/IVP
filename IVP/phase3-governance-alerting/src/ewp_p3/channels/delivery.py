"""Delivery receipt tracking and Critical-channel safety rule."""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DeliveryReceipt:
    alert_id: str
    channel: str
    sent_at: datetime
    success: bool
    reach: int = 0
    detail: str = ""


def required_channels(level: str, configured: dict[str, list[str]]) -> list[str]:
    channels = configured.get(level.lower(), [])
    if level == "CRITICAL" and len(channels) < 2:
        raise ValueError("Critical alerts require at least two configured channels")
    return list(channels)


def receipt(alert_id: str, channel: str, success: bool, reach: int = 0, detail: str = "") -> DeliveryReceipt:
    return DeliveryReceipt(alert_id, channel, datetime.now(timezone.utc), success, reach, detail)
