"""Health check endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response

from jobradar.api import deps as deps_module

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(response: Response) -> dict[str, Any]:
    """Health check endpoint for uptime monitoring.

    Returns basic status and last successful sync time.
    Does not require authentication.
    """
    db = deps_module.get_db()
    last_sync = await db.get_latest_sync_time()

    return {
        "status": "ok",
        "last_successful_sync": last_sync.isoformat() if last_sync else None,
    }