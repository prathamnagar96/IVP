"""CLI entry points for sync operations."""

from __future__ import annotations

import asyncio
import logging
import sys

import click

from jobradar.config import get_settings
from jobradar.pipeline.run import run_ats_sync, run_full_sync, run_scraper_sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """JobRadar CLI commands."""
    pass


@cli.command()
def sync_ats():
    """Run ATS sync (Greenhouse, Lever, Ashby)."""
    asyncio.run(_run_ats_sync())


async def _run_ats_sync():
    try:
        result = await run_ats_sync()
        _print_result("ATS Sync", result)
        sys.exit(0 if result.sources_failed == 0 else 1)
    except Exception as e:
        logger.exception(f"ATS sync failed: {e}")
        sys.exit(1)


@cli.command()
def sync_scrape():
    """Run scraper sync (fallback HTML scraping)."""
    asyncio.run(_run_scraper_sync())


async def _run_scraper_sync():
    try:
        result = await run_scraper_sync()
        _print_result("Scraper Sync", result)
        sys.exit(0 if result.sources_failed == 0 else 1)
    except Exception as e:
        logger.exception(f"Scraper sync failed: {e}")
        sys.exit(1)


@cli.command()
def sync_full():
    """Run both ATS and scraper syncs."""
    asyncio.run(_run_full_sync())


async def _run_full_sync():
    try:
        ats_result, scraper_result = await run_full_sync()
        _print_result("ATS Sync", ats_result)
        _print_result("Scraper Sync", scraper_result)

        # Exit with error if either failed
        if ats_result.sources_failed > 0 or scraper_result.sources_failed > 0:
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Full sync failed: {e}")
        sys.exit(1)


def _print_result(name: str, result):
    """Print sync result summary."""
    click.echo(f"\n{name} Results:")
    click.echo(f"  Sources total:     {result.sources_total}")
    click.echo(f"  Sources succeeded: {result.sources_succeeded}")
    click.echo(f"  Sources failed:    {result.sources_failed}")
    click.echo(f"  Sources disabled:  {result.sources_disabled}")
    click.echo(f"  Jobs added:        {result.jobs_added}")
    click.echo(f"  Jobs updated:      {result.jobs_updated}")
    click.echo(f"  Jobs expired:      {result.jobs_expired}")

    if result.failed_sources:
        click.echo("  Failed sources:")
        for src, err in result.failed_sources:
            click.echo(f"    - {src}: {err}")

    if result.disabled_sources:
        click.echo("  Disabled sources:")
        for src in result.disabled_sources:
            click.echo(f"    - {src}")


if __name__ == "__main__":
    cli()