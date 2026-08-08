"""Normalization and deduplication utilities."""

from __future__ import annotations

import hashlib
import re
from typing import Any


def clean_string(s: str) -> str:
    """Normalize string for dedup hashing: lowercase, strip, remove punctuation, collapse whitespace."""
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)  # Replace punctuation with spaces
    s = re.sub(r"\s+", " ", s).strip()  # Collapse whitespace and trim ends
    return s


def normalize_key(company: str, title: str, location: str) -> str:
    """Create normalized key for fingerprinting."""
    return f"{clean_string(company)}|{clean_string(title)}|{clean_string(location)}"


def fingerprint(company: str, title: str, location: str) -> str:
    """Generate SHA-256 fingerprint hash for deduplication."""
    key = normalize_key(company, title, location)
    return hashlib.sha256(key.encode()).hexdigest()


def raw_job_to_db_dict(raw_job: Any, fp_hash: str | None = None) -> dict[str, Any]:
    """Convert RawJob to database dict with fingerprint hash."""
    if fp_hash is None:
        fp_hash = fingerprint(raw_job.company, raw_job.title, raw_job.location or "")

    return {
        "fingerprint_hash": fp_hash,
        "title": raw_job.title.strip(),
        "company": raw_job.company.strip(),
        "company_url": raw_job.company_url,
        "location": (raw_job.location or "Remote").strip(),
        "tags": [],  # Will be filled by enrichment
        "min_salary": None,  # Will be filled by enrichment
        "max_salary": None,
        "apply_url": raw_job.apply_url.strip(),
        "source": raw_job.source,
        "posted_at": raw_job.posted_at,
        "last_seen_at": raw_job.posted_at,  # Use posted_at as initial last_seen
    }