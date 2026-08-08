"""Fallback HTML scraper connector for non-ATS sources.

Uses httpx + BeautifulSoup first, falls back to Playwright for JS-rendered pages.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from jobradar.config import SourceConfig
from jobradar.connectors.base import Connector, ConnectorError, RawJob, parse_iso_datetime


class ScraperConnector(Connector):
    """Fallback scraper for companies without ATS APIs.

    Each source needs CSS selectors configured in sources.yaml.
    """

    source_id = "scrape:custom"
    REQUEST_TIMEOUT = 30.0

    def __init__(
        self,
        source_config: SourceConfig,
        http_client: httpx.AsyncClient | None = None,
        headless: bool = True,
        scraper_timeout: int = 30000,
        user_agent: str = "JobRadar/1.0 (+https://jobradar.example.com/bot)",
    ):
        self.source_config = source_config
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self.headless = headless
        self.scraper_timeout = scraper_timeout
        self.user_agent = user_agent
        self._playwright = None
        self._browser = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.REQUEST_TIMEOUT),
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
        return self._http_client

    async def _get_playwright_browser(self):
        """Lazy-initialize Playwright browser."""
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
        return self._browser

    async def close(self):
        if self._owns_http_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def fetch(self, company: str, token: str) -> list[RawJob]:
        """Fetch jobs by scraping the careers page.

        Args:
            company: Company display name
            token: URL of the careers page (from sources.yaml token field)

        Returns:
            List of RawJob objects
        """
        url = token  # For scrape sources, token is the URL
        selectors = self.source_config.scrape_selectors

        if not selectors:
            raise ConnectorError(
                "No scrape_selectors configured for this source",
                source=self.source_id,
                details={"company": company, "url": url},
            )

        # Try static HTML first (faster, lighter)
        jobs = await self._try_static_scrape(url, selectors, company)
        if jobs:
            return jobs

        # Fall back to Playwright for JS-rendered content
        return await self._try_playwright_scrape(url, selectors, company)

    async def _try_static_scrape(
        self, url: str, selectors: dict[str, str], company: str
    ) -> list[RawJob]:
        """Try scraping with httpx + BeautifulSoup."""
        client = await self._get_http_client()

        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.RequestError as e:
            return []  # Will fall back to Playwright

        soup = BeautifulSoup(response.text, "lxml")
        return self._parse_job_list(soup, url, selectors, company)

    async def _try_playwright_scrape(
        self, url: str, selectors: dict[str, str], company: str
    ) -> list[RawJob]:
        """Scrape using Playwright for JS-rendered pages."""
        browser = await self._get_playwright_browser()
        context = await browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=self.scraper_timeout)
            # Wait for job list to appear
            job_list_selector = selectors.get("job_list", ".job-card")
            await page.wait_for_selector(job_list_selector, timeout=10000)

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")
            return self._parse_job_list(soup, url, selectors, company)

        except Exception as e:
            raise ConnectorError(
                f"Playwright scrape failed: {e}",
                source=self.source_id,
                details={"company": company, "url": url},
            ) from e
        finally:
            await page.close()
            await context.close()

    def _parse_job_list(
        self, soup: BeautifulSoup, base_url: str, selectors: dict[str, str], company: str
    ) -> list[RawJob]:
        """Parse job listings from BeautifulSoup object."""
        job_list_selector = selectors.get("job_list", ".job-card")
        job_elements = soup.select(job_list_selector)

        if not job_elements:
            return []

        raw_jobs = []
        for elem in job_elements:
            try:
                job = self._parse_job_element(elem, base_url, selectors, company)
                if job:
                    raw_jobs.append(job)
            except Exception as e:
                print(f"Warning: Failed to parse job element for {company}: {e}")
                continue

        return raw_jobs

    def _parse_job_element(
        self, elem: BeautifulSoup, base_url: str, selectors: dict[str, str], company: str
    ) -> RawJob | None:
        """Parse a single job element."""
        # Title (required)
        title_selector = selectors.get("title", "h3, h2, .title")
        title_elem = elem.select_one(title_selector)
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)

        # Location
        location_selector = selectors.get("location", ".location")
        location_elem = elem.select_one(location_selector)
        location = location_elem.get_text(strip=True) if location_elem else None

        # Description
        desc_selector = selectors.get("description", ".description")
        desc_elem = elem.select_one(desc_selector)
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Apply URL
        apply_selector = selectors.get("apply_url", "a[href*='apply'], a[href*='career']")
        apply_elem = elem.select_one(apply_selector)
        apply_url = ""
        if apply_elem and apply_elem.get("href"):
            apply_url = urljoin(base_url, apply_elem["href"])

        # Posted date
        date_selector = selectors.get("posted_date", ".date, time")
        date_elem = elem.select_one(date_selector)
        posted_at = None
        if date_elem:
            # Try datetime attribute first
            datetime_attr = date_elem.get("datetime") or date_elem.get("data-date")
            if datetime_attr:
                posted_at = parse_iso_datetime(datetime_attr)
            else:
                # Try parsing text
                date_text = date_elem.get_text(strip=True)
                posted_at = self._parse_date_text(date_text)

        # Company URL - try to find from page or use base
        company_url = None
        # Could extract from a logo link or company name link

        return RawJob(
            title=title,
            company=company,
            company_url=company_url,
            location=location,
            description=description,
            salary_structured=None,
            salary_text=description,  # Use description for regex salary extraction
            apply_url=apply_url,
            posted_at=posted_at,
            source=f"{self.source_id}:{self.source_config.token}",
        )

    def _parse_date_text(self, text: str) -> datetime | None:
        """Parse various date formats from text."""
        if not text:
            return None

        # Common patterns
        patterns = [
            r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD
            r"(\d{2}/\d{2}/\d{4})",  # MM/DD/YYYY
            r"(\d{2}-\d{2}-\d{4})",  # MM-DD-YYYY
            r"(\w+ \d{1,2}, \d{4})",  # Month DD, YYYY
            r"(\d{1,2} \w+ \d{4})",  # DD Month YYYY
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return parse_iso_datetime(match.group(1))
                except Exception:
                    continue

        return None