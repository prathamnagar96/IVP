"""Database client using Supabase (PostgreSQL)."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from jobradar.config import Settings, get_settings
from jobradar.db.models import Base, Job, SourceHealth, SyncRun


def _ensure_aiosqlite_compat() -> None:
    """Patch aiosqlite for SQLAlchemy 2.0 compatibility in this environment."""
    try:
        import aiosqlite
    except ImportError:
        return

    candidates: list[type[Any]] = []
    connection_cls = getattr(aiosqlite, "Connection", None)
    if connection_cls is not None:
        candidates.append(connection_cls)
    if hasattr(aiosqlite, "core"):
        core_connection_cls = getattr(aiosqlite.core, "Connection", None)
        if core_connection_cls is not None and core_connection_cls not in candidates:
            candidates.append(core_connection_cls)

    for candidate in candidates:
        if hasattr(candidate, "create_function"):
            continue

        async def create_function(self: Any, *args: Any, **kwargs: Any) -> Any:
            return self._connection.create_function(*args, **kwargs)

        setattr(candidate, "create_function", create_function)


_ensure_aiosqlite_compat()


class DatabaseClient:
    """Async database client for JobRadar."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._engine = None
        self._session_factory = None

    @property
    def engine(self):
        if self._engine is None:
            raw_url = (self.settings.supabase_url or "").strip()
            if not raw_url:
                raw_url = "sqlite+aiosqlite:///./jobradar_local.db"

            if raw_url.startswith("postgresql://"):
                # Supabase uses postgresql:// URLs, convert to asyncpg
                db_url = raw_url.replace("postgresql://", "postgresql+asyncpg://")
                # Supabase requires the service role key as password
                # The URL format: postgresql://postgres:[password]@host:port/dbname
                # We need to inject the key into the URL
                if "@" in db_url:
                    # Replace password with service role key
                    parts = db_url.split("@")
                    prefix = parts[0].rsplit(":", 1)[0]
                    db_url = f"{prefix}:{self.settings.supabase_key}@{parts[1]}"
                self._engine = create_async_engine(
                    db_url,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    echo=False,
                )
            elif raw_url.startswith("sqlite"):
                _ensure_aiosqlite_compat()
                self._engine = create_async_engine(
                    raw_url,
                    echo=False,
                    connect_args={"check_same_thread": False},
                )
            else:
                raise ValueError(f"Unsupported database URL: {raw_url}")
        return self._engine

    @property
    def session_factory(self):
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
        return self._session_factory

    @asynccontextmanager
    async def session(self):
        """Get a database session."""
        async with self.session_factory() as session:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self):
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    # --- Job operations ---

    async def upsert_jobs(self, jobs: list[dict[str, Any]]) -> tuple[int, int]:
        """Upsert jobs using fingerprint_hash for deduplication.

        Returns:
            (added_count, updated_count)
        """
        if not jobs:
            return (0, 0)

        added = 0
        updated = 0

        async with self.session() as session:
            for job_data in jobs:
                # Use PostgreSQL ON CONFLICT for upsert
                stmt = pg_insert(Job).values(**job_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["fingerprint_hash"],
                    set_={
                        "title": stmt.excluded.title,
                        "company": stmt.excluded.company,
                        "company_url": stmt.excluded.company_url,
                        "location": stmt.excluded.location,
                        "tags": stmt.excluded.tags,
                        "min_salary": stmt.excluded.min_salary,
                        "max_salary": stmt.excluded.max_salary,
                        "apply_url": stmt.excluded.apply_url,
                        "source": stmt.excluded.source,
                        "posted_at": stmt.excluded.posted_at,
                        "last_seen_at": stmt.excluded.last_seen_at,
                        "status": "active",  # Reactivate if seen again
                    },
                ).returning(Job.id, Job.fingerprint_hash)

                result = await session.execute(stmt)
                row = result.fetchone()
                if row:
                    # Check if this was an insert or update by checking created_at
                    # For simplicity, we'll count all as added and track updated separately
                    # In practice, you'd need to check if the row existed before
                    pass

            await session.commit()

        # For accurate counts, we'd need a more complex query
        # For now, return approximate counts
        return (len(jobs), 0)

    async def upsert_jobs_detailed(
        self, jobs: list[dict[str, Any]]
    ) -> tuple[int, int]:
        """Upsert jobs with accurate added/updated counts."""
        if not jobs:
            return (0, 0)

        added = 0
        updated = 0

        async with self.session() as session:
            for job_data in jobs:
                fingerprint = job_data["fingerprint_hash"]

                # Check if exists
                existing = await session.execute(
                    select(Job.id).where(Job.fingerprint_hash == fingerprint)
                )
                exists = existing.scalar_one_or_none()

                # Prepare update data (always update last_seen_at and status=active)
                update_data = {
                    **job_data,
                    "last_seen_at": datetime.utcnow(),
                    "status": "active",
                }

                if exists:
                    # Update existing
                    await session.execute(
                        update(Job)
                        .where(Job.fingerprint_hash == fingerprint)
                        .values(**update_data)
                    )
                    updated += 1
                else:
                    # Insert new
                    new_job = Job(**update_data)
                    session.add(new_job)
                    added += 1

            await session.commit()

        return (added, updated)

    async def expire_stale_jobs(
        self, source: str, expiry_days: int, since: datetime
    ) -> int:
        """Mark jobs from a source as expired if not seen since the given date."""
        async with self.session() as session:
            result = await session.execute(
                update(Job)
                .where(
                    Job.source == source,
                    Job.status == "active",
                    Job.last_seen_at < since,
                )
                .values(status="expired")
            )
            await session.commit()
            return result.rowcount

    async def get_active_jobs(
        self,
        tag: str | None = None,
        company: str | None = None,
        min_salary: int | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> tuple[list[Job], int]:
        """Get paginated active jobs with filters."""
        async with self.session() as session:
            query = select(Job).where(Job.status == "active")

            if company:
                query = query.where(Job.company.ilike(f"%{company}%"))
            if min_salary:
                query = query.where(Job.min_salary >= min_salary)

            result = await session.execute(query.order_by(Job.posted_at.desc().nullslast()))
            jobs = list(result.scalars().all())

            if tag:
                jobs = [job for job in jobs if tag.lower() in {t.lower() for t in (job.tags or [])}]

            total = len(jobs)
            offset = (page - 1) * limit
            paged_jobs = jobs[offset : offset + limit]

            return paged_jobs, total

    async def get_latest_sync_time(self) -> datetime | None:
        """Get the timestamp of the last successful sync."""
        async with self.session() as session:
            result = await session.execute(
                select(SyncRun.completed_at)
                .where(SyncRun.completed_at.is_not(None))
                .order_by(SyncRun.completed_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    # --- Source health operations ---

    async def record_source_success(self, source_id: str):
        """Record successful sync for a source."""
        async with self.session() as session:
            stmt = pg_insert(SourceHealth).values(
                source_id=source_id,
                consecutive_failures=0,
                disabled=False,
                last_success_at=datetime.utcnow(),
                last_run_at=datetime.utcnow(),
                last_error=None,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["source_id"],
                set_={
                    "consecutive_failures": 0,
                    "disabled": False,
                    "last_success_at": stmt.excluded.last_success_at,
                    "last_run_at": stmt.excluded.last_run_at,
                    "last_error": None,
                    "updated_at": datetime.utcnow(),
                },
            )
            await session.execute(stmt)
            await session.commit()

    async def record_source_failure(self, source_id: str, error: str) -> int:
        """Record failed sync for a source. Returns new failure count."""
        async with self.session() as session:
            # Get current state
            result = await session.execute(
                select(SourceHealth).where(SourceHealth.source_id == source_id)
            )
            health = result.scalar_one_or_none()

            if health:
                new_failures = health.consecutive_failures + 1
                disabled = new_failures >= 3

                await session.execute(
                    update(SourceHealth)
                    .where(SourceHealth.source_id == source_id)
                    .values(
                        consecutive_failures=new_failures,
                        disabled=disabled,
                        last_run_at=datetime.utcnow(),
                        last_error=error[:500],  # Truncate long errors
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                new_failures = 1
                await session.execute(
                    pg_insert(SourceHealth).values(
                        source_id=source_id,
                        consecutive_failures=1,
                        disabled=False,
                        last_run_at=datetime.utcnow(),
                        last_error=error[:500],
                    )
                )

            await session.commit()
            return new_failures

    async def is_source_disabled(self, source_id: str) -> bool:
        """Check if a source is disabled."""
        async with self.session() as session:
            result = await session.execute(
                select(SourceHealth.disabled).where(SourceHealth.source_id == source_id)
            )
            return result.scalar_one_or_none() or False

    async def get_failed_sources(self, threshold: int = 3) -> list[SourceHealth]:
        """Get sources with consecutive failures >= threshold."""
        async with self.session() as session:
            result = await session.execute(
                select(SourceHealth).where(SourceHealth.consecutive_failures >= threshold)
            )
            return list(result.scalars().all())

    async def reenable_source(self, source_id: str):
        """Manually re-enable a disabled source."""
        async with self.session() as session:
            await session.execute(
                update(SourceHealth)
                .where(SourceHealth.source_id == source_id)
                .values(disabled=False, consecutive_failures=0, updated_at=datetime.utcnow())
            )
            await session.commit()

    # --- Sync run operations ---

    async def create_sync_run(self, run_type: str, sources_total: int) -> uuid.UUID:
        """Create a new sync run record."""
        async with self.session() as session:
            run = SyncRun(
                run_type=run_type,
                sources_total=sources_total,
                sources_succeeded=0,
                sources_failed=0,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run.id

    async def complete_sync_run(
        self,
        run_id: uuid.UUID,
        succeeded: int,
        failed: int,
        disabled: int,
        jobs_added: int,
        jobs_updated: int,
        jobs_expired: int,
        error_message: str | None = None,
    ):
        """Complete a sync run record."""
        async with self.session() as session:
            await session.execute(
                update(SyncRun)
                .where(SyncRun.id == run_id)
                .values(
                    sources_succeeded=succeeded,
                    sources_failed=failed,
                    sources_disabled=disabled,
                    jobs_added=jobs_added,
                    jobs_updated=jobs_updated,
                    jobs_expired=jobs_expired,
                    completed_at=datetime.utcnow(),
                    error_message=error_message,
                )
            )
            await session.commit()


# Global instance
_db_client: DatabaseClient | None = None


def get_db_client() -> DatabaseClient:
    """Get or create the global database client."""
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client