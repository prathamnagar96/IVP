"""Listing lifecycle management: expiry sweep."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from jobradar.db.client import DatabaseClient


async def expire_stale_listings(
    db: DatabaseClient,
    sources: list[str],
    expiry_days: int,
    run_timestamp: datetime | None = None,
) -> dict[str, int]:
    """Mark listings as expired if not seen in recent sync.

    Args:
        db: Database client
        sources: List of source IDs to check
        expiry_days: Days after last_seen_at to mark expired
        run_timestamp: Timestamp of current run (defaults to now)

    Returns:
        Dict mapping source_id to count of expired listings
    """
    if run_timestamp is None:
        run_timestamp = datetime.utcnow()

    cutoff = run_timestamp - timedelta(days=expiry_days)
    results = {}

    for source_id in sources:
        count = await db.expire_stale_jobs(source_id, expiry_days, cutoff)
        results[source_id] = count

    return results


async def get_active_sources(db: DatabaseClient) -> list[str]:
    """Get list of sources that have active jobs."""
    # This would require a query - for now return empty
    # In practice, you'd track this from the sync run
    return []