"""Pipeline orchestration for sync runs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from jobradar.alerts.webhook import send_run_summary
from jobradar.config import SourceConfig, load_sources, get_settings
from jobradar.connectors import ConnectorError, create_connector
from jobradar.db.client import DatabaseClient, get_db_client
from jobradar.pipeline.enrich import enrich_job
from jobradar.pipeline.lifecycle import expire_stale_listings
from jobradar.pipeline.normalize import fingerprint, raw_job_to_db_dict
from jobradar.pipeline.sync_result import SyncResult

logger = logging.getLogger(__name__)


async def run_ats_sync(
    db: DatabaseClient | None = None,
    sources: list[SourceConfig] | None = None,
    settings=None,
) -> SyncResult:
    """Run ATS sync for all enabled ATS sources."""
    settings = settings or get_settings()
    db = db or get_db_client()
    sources = sources or [s for s in load_sources() if s.ats in ("greenhouse", "lever", "ashby")]

    result = SyncResult()
    result.sources_total = len(sources)

    run_id = await db.create_sync_run("ats", result.sources_total)
    run_started = datetime.utcnow()

    # Track which sources we actually processed (for expiry)
    processed_sources = []

    for source in sources:
        source_id = f"{source.ats}:{source.token}"

        # Check if source is disabled
        if await db.is_source_disabled(source_id):
            result.sources_disabled += 1
            result.disabled_sources.append(source_id)
            logger.info(f"Skipping disabled source: {source_id}")
            continue

        try:
            # Create connector
            connector = create_connector(source)

            # Fetch jobs
            logger.info(f"Fetching jobs from {source.company} ({source_id})")
            raw_jobs = await connector.fetch(source.company, source.token)

            # Process jobs
            if raw_jobs:
                await _process_raw_jobs(db, raw_jobs, source_id, result)

            # Record success
            await db.record_source_success(source_id)
            result.sources_succeeded += 1
            processed_sources.append(source_id)

            await connector.close()

        except ConnectorError as e:
            error_msg = str(e)
            result.sources_failed += 1
            result.failed_sources.append((source_id, error_msg))

            # Record failure
            failure_count = await db.record_source_failure(source_id, error_msg)
            if failure_count >= 3:
                result.sources_disabled += 1
                result.disabled_sources.append(source_id)
                logger.warning(f"Source {source_id} disabled after {failure_count} failures")

            logger.error(f"Failed to fetch from {source_id}: {error_msg}")

        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            result.sources_failed += 1
            result.failed_sources.append((source_id, error_msg))

            failure_count = await db.record_source_failure(source_id, error_msg)
            if failure_count >= 3:
                result.sources_disabled += 1
                result.disabled_sources.append(source_id)

            logger.exception(f"Unexpected error for {source_id}")

    # Expiry sweep for processed sources
    if processed_sources:
        expiry_results = await expire_stale_listings(
            db, processed_sources, settings.expiry_days, run_started
        )
        result.jobs_expired = sum(expiry_results.values())

    # Complete sync run
    await db.complete_sync_run(
        run_id=run_id,
        succeeded=result.sources_succeeded,
        failed=result.sources_failed,
        disabled=result.sources_disabled,
        jobs_added=result.jobs_added,
        jobs_updated=result.jobs_updated,
        jobs_expired=result.jobs_expired,
    )

    # Send summary alert
    await send_run_summary(settings, result, run_started)

    return result


async def _process_raw_jobs(
    db: DatabaseClient,
    raw_jobs: list[Any],
    source_id: str,
    result: SyncResult,
):
    """Process raw jobs through normalize, enrich, and upsert."""
    if not raw_jobs:
        return

    enriched_jobs = []
    for raw_job in raw_jobs:
        try:
            # Normalize
            fp_hash = fingerprint(raw_job.company, raw_job.title, raw_job.location or "")
            job_dict = raw_job_to_db_dict(raw_job, fp_hash)

            # Enrich
            job_dict = enrich_job(job_dict, raw_job)

            enriched_jobs.append(job_dict)
        except Exception as e:
            logger.warning(f"Failed to process job from {source_id}: {e}")
            continue

    if enriched_jobs:
        added, updated = await db.upsert_jobs_detailed(enriched_jobs)
        result.jobs_added += added
        result.jobs_updated += updated


async def run_scraper_sync(
    db: DatabaseClient | None = None,
    sources: list[SourceConfig] | None = None,
    settings=None,
    headless: bool = True,
    scraper_timeout: int = 30000,
    user_agent: str = "JobRadar/1.0 (+https://jobradar.example.com/bot)",
) -> SyncResult:
    """Run scraper sync for all enabled scrape sources."""
    settings = settings or get_settings()
    db = db or get_db_client()
    sources = sources or [s for s in load_sources() if s.ats == "scrape"]

    result = SyncResult()
    result.sources_total = len(sources)

    run_id = await db.create_sync_run("scrape", result.sources_total)
    run_started = datetime.utcnow()

    processed_sources = []

    for source in sources:
        source_id = f"scrape:custom:{source.token}"

        if await db.is_source_disabled(source_id):
            result.sources_disabled += 1
            result.disabled_sources.append(source_id)
            logger.info(f"Skipping disabled scraper source: {source_id}")
            continue

        try:
            connector = create_connector(
                source,
                headless=headless,
                scraper_timeout=scraper_timeout,
                user_agent=user_agent,
            )

            logger.info(f"Scraping jobs from {source.company} ({source_id})")
            raw_jobs = await connector.fetch(source.company, source.token)

            if raw_jobs:
                await _process_raw_jobs(db, raw_jobs, source_id, result)

            await db.record_source_success(source_id)
            result.sources_succeeded += 1
            processed_sources.append(source_id)

            await connector.close()

        except ConnectorError as e:
            error_msg = str(e)
            result.sources_failed += 1
            result.failed_sources.append((source_id, error_msg))

            failure_count = await db.record_source_failure(source_id, error_msg)
            if failure_count >= 3:
                result.sources_disabled += 1
                result.disabled_sources.append(source_id)
                logger.warning(f"Scraper source {source_id} disabled after {failure_count} failures")

            logger.error(f"Failed to scrape {source_id}: {error_msg}")

        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            result.sources_failed += 1
            result.failed_sources.append((source_id, error_msg))

            failure_count = await db.record_source_failure(source_id, error_msg)
            if failure_count >= 3:
                result.sources_disabled += 1
                result.disabled_sources.append(source_id)

            logger.exception(f"Unexpected error for scraper {source_id}")

    # Expiry sweep
    if processed_sources:
        expiry_results = await expire_stale_listings(
            db, processed_sources, settings.expiry_days, run_started
        )
        result.jobs_expired = sum(expiry_results.values())

    # Complete sync run
    await db.complete_sync_run(
        run_id=run_id,
        succeeded=result.sources_succeeded,
        failed=result.sources_failed,
        disabled=result.sources_disabled,
        jobs_added=result.jobs_added,
        jobs_updated=result.jobs_updated,
        jobs_expired=result.jobs_expired,
    )

    await send_run_summary(settings, result, run_started)

    return result


async def run_full_sync(
    db: DatabaseClient | None = None,
    settings=None,
) -> tuple[SyncResult, SyncResult]:
    """Run both ATS and scraper syncs sequentially."""
    ats_result = await run_ats_sync(db, settings=settings)
    scraper_result = await run_scraper_sync(db, settings=settings)
    return ats_result, scraper_result