"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from jobradar.api.deps import get_db
from jobradar.api.routes.health import router as health_router
from jobradar.api.routes.jobs import router as jobs_router
from jobradar.api.deps import reset_rate_limit_store
from jobradar.config import Settings, get_settings, set_settings
from jobradar.db.client import DatabaseClient, get_db_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting JobRadar API...")
    db = get_db_client()
    # Verify database connectivity with a SQLAlchemy-compatible statement.
    try:
        async with db.session() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down JobRadar API...")
    await db.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = settings or get_settings()
    set_settings(settings)
    reset_rate_limit_store()

    app = FastAPI(
        title="JobRadar API",
        description="Remote software engineering jobs at funded startups",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.log_level == "DEBUG" else None,
        redoc_url=None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # Global exception handler for consistent error format
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled error: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Internal server error",
                "code": "internal_error",
            },
        )

    # Include routers
    app.include_router(health_router)
    app.include_router(jobs_router)

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        return {
            "name": "JobRadar API",
            "version": "1.0.0",
            "docs": "/docs",
        }

    return app


# Create app instance for uvicorn
app = create_app()