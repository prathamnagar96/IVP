"""Jobs API endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response

from jobradar.api import deps as deps_module
from jobradar.api.deps import PaginationParams, rate_limit

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.get("/jobs")
async def list_jobs(
    request: Request,
    response: Response,
    tag: Annotated[str | None, Query(description="Filter by tech tag")] = None,
    company: Annotated[str | None, Query(description="Filter by company name (partial match)")] = None,
    min_salary: Annotated[int | None, Query(description="Minimum salary (USD)", ge=0)] = None,
    limit: Annotated[int, Query(description="Results per page")] = 50,
    page: Annotated[int, Query(description="Page number")] = 1,
    _rate_limit: None = Depends(rate_limit),
) -> dict[str, Any]:
    """Get paginated list of active job listings.

    Requires authentication via X-RapidAPI-Proxy-Secret or X-API-Key header.
    """
    safe_limit = max(1, min(limit, 100))
    safe_page = max(1, page)

    db = deps_module.get_db()
    jobs, total = await db.get_active_jobs(
        tag=tag,
        company=company,
        min_salary=min_salary,
        limit=safe_limit,
        page=safe_page,
    )

    # Add rate limit headers from dependency
    if hasattr(request.state, "rate_limit_headers"):
        for key, value in request.state.rate_limit_headers.items():
            response.headers[key] = value

    return {
        "status": "success",
        "page": safe_page,
        "limit": safe_limit,
        "total_records": total,
        "data": [job.to_dict() for job in jobs],
    }


@router.get("/jobs/{job_id}")
async def get_job(
    request: Request,
    response: Response,
    job_id: str,
    _rate_limit: None = Depends(rate_limit),
) -> dict[str, Any]:
    """Get a single job by ID."""
    from uuid import UUID
    from sqlalchemy import select
    from jobradar.db.models import Job

    try:
        job_uuid = UUID(job_id)
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid job ID format",
            "code": "invalid_parameter",
        }

    db = deps_module.get_db()
    async with db.session() as session:
        result = await session.execute(
            select(Job).where(Job.id == job_uuid, Job.status == "active")
        )
        job = result.scalar_one_or_none()

    if not job:
        return {
            "status": "error",
            "message": "Job not found",
            "code": "not_found",
        }

    # Add rate limit headers
    if hasattr(request.state, "rate_limit_headers"):
        for key, value in request.state.rate_limit_headers.items():
            response.headers[key] = value

    return {
        "status": "success",
        "data": job.to_dict(),
    }