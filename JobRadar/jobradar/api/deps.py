"""API dependencies: authentication and rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from jobradar.config import Settings, get_settings
from jobradar.db.client import DatabaseClient, get_db_client


def reset_rate_limit_store() -> None:
    """Clear in-memory rate limiting state for a fresh app instance."""
    _rate_limit_store.clear()

# Rate limit storage (in-memory, per-process)
# In production with multiple workers, use Redis
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

# Auth header names
RAPIDAPI_PROXY_SECRET_HEADER = "X-RapidAPI-Proxy-Secret"
API_KEY_HEADER = "X-API-Key"


async def verify_auth(
    request: Request,
    rapidapi_secret: Annotated[str | None, Header(alias=RAPIDAPI_PROXY_SECRET_HEADER)] = None,
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
    settings: Settings = Depends(get_settings),
) -> str:
    """Verify authentication via RapidAPI proxy secret or API key.

    Returns the authenticated key identifier for rate limiting.
    """
    # Check RapidAPI proxy secret first (when called via RapidAPI gateway)
    if rapidapi_secret and settings.rapidapi_proxy_secret:
        if rapidapi_secret == settings.rapidapi_proxy_secret:
            return "rapidapi"

    # Check API key
    if api_key and api_key in settings.api_key_list:
        return api_key

    # No valid auth
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "ApiKey"},
    )


async def rate_limit(
    request: Request,
    auth_id: str = Depends(verify_auth),
    settings: Settings = Depends(get_settings),
) -> None:
    """Apply rate limiting based on authenticated identity."""
    now = time.time()
    window = settings.rate_limit_window
    limit = settings.rate_limit_requests

    # Clean old entries
    cutoff = now - window
    _rate_limit_store[auth_id] = [
        t for t in _rate_limit_store[auth_id] if t > cutoff
    ]

    # Check limit
    if len(_rate_limit_store[auth_id]) >= limit:
        oldest = _rate_limit_store[auth_id][0]
        reset_time = int(oldest + window)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(max(1, int(reset_time - now))),
            },
        )

    # Add current request
    _rate_limit_store[auth_id].append(now)

    # Add rate limit headers to response
    remaining = limit - len(_rate_limit_store[auth_id])
    reset_time = int(now + window)
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time),
    }


def get_db() -> DatabaseClient:
    """Get database client dependency."""
    return get_db_client()


class PaginationParams:
    """Pagination and filter parameters for jobs endpoint."""

    def __init__(
        self,
        tag: str | None = None,
        company: str | None = None,
        min_salary: int | None = None,
        limit: int = 50,
        page: int = 1,
    ):
        self.tag = tag
        self.company = company
        self.min_salary = min_salary
        self.limit = min(max(limit, 1), 100)  # Clamp 1-100
        self.page = max(page, 1)  # Minimum page 1
        self.offset = (self.page - 1) * self.limit