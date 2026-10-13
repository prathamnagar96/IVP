"""Small, standards-shaped CAP v1.2 builder with explicit safety defaults."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from xml.etree.ElementTree import fromstring

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
LEVELS = {
    "ADVISORY": ("Future", "Minor", "Possible", "Monitor / Prepare", "Advisory"),
    "WARNING": ("Expected", "Moderate", "Likely", "Prepare", "Warning"),
    "CRITICAL": ("Immediate", "Severe", "Likely", "Evacuate", "Critical"),
    "ALL_CLEAR": ("Past", "Minor", "Observed", "AllClear", "All clear"),
}


def build_cap(
    *,
    identifier: str,
    sender: str,
    level: str,
    area_description: str,
    polygon: list[tuple[float, float]],
    headline: str,
    description: str,
    instruction: str,
    expires: datetime,
    mode: str = "Exercise",
    language: str = "en",
    references: str | None = None,
    msg_type: str = "Alert",
) -> str:
    """Build CAP XML; callers must supply a closed polygon and non-empty action text."""
    if level not in LEVELS:
        raise ValueError(f"unsupported CAP level: {level}")
    if mode not in {"Exercise", "Test", "Actual"}:
        raise ValueError("mode must be Exercise, Test, or Actual")
    if len(polygon) < 4 or polygon[0] != polygon[-1]:
        raise ValueError("CAP polygon must contain at least four points and be closed")
    if any(not text.strip() for text in (headline, description, instruction, area_description)):
        raise ValueError("CAP text fields must not be empty")
    urgency, severity, certainty, response, _ = LEVELS[level]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    points = " ".join(f"{lat:.8f},{lon:.8f}" for lat, lon in polygon)
    def tag(name: str, value: str) -> str:
        return f"<{name}>{escape(value)}</{name}>"
    reference_xml = tag("references", references) if references else ""
    return (
        f'<alert xmlns="{CAP_NS}">'
        f"{tag('identifier', identifier)}{tag('sender', sender)}"
        f"{tag('sent', datetime.now(timezone.utc).isoformat())}"
        f"{tag('status', mode)}{tag('msgType', msg_type)}{tag('scope', 'Public')}"
        f"<info>{tag('language', language)}{tag('category', 'Geo')}"
        f"{tag('event', 'Landslide')}{tag('responseType', response)}"
        f"{tag('urgency', urgency)}{tag('severity', severity)}{tag('certainty', certainty)}"
        f"{tag('expires', expires.isoformat())}{tag('senderName', sender)}"
        f"{tag('headline', headline)}{tag('description', description)}"
        f"{tag('instruction', instruction)}<area>{tag('areaDesc', area_description)}"
        f"{tag('polygon', points)}</area></info>{reference_xml}</alert>"
    )


def validate_cap(xml: str) -> None:
    """Validate required CAP structure without silently accepting malformed XML."""
    root = fromstring(xml)
    required = {"identifier", "sender", "sent", "status", "msgType", "scope", "info"}
    names = {child.tag.rsplit("}", 1)[-1] for child in root}
    missing = required - names
    if root.tag.rsplit("}", 1)[-1] != "alert" or missing:
        raise ValueError(f"invalid CAP message; missing: {sorted(missing)}")
