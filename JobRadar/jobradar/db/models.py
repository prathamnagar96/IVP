"""SQLAlchemy models for JobRadar database."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


def _coerce_datetime(value: datetime | str | None) -> datetime | None:
    """Normalize datetime-like values coming from tests or external APIs."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    return value


class Job(Base):
    """Job listing model."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    fingerprint_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str] = mapped_column(String(255), default="Remote", nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    min_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    apply_url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False, index=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_jobs_status_last_seen", "status", "last_seen_at"),
        Index("ix_jobs_posted_at", "posted_at"),
        Index("ix_jobs_tags", "tags"),
    )

    def __init__(self, **kwargs):
        for field in ("posted_at", "last_seen_at", "created_at"):
            if field in kwargs:
                kwargs[field] = _coerce_datetime(kwargs[field])
        super().__init__(**kwargs)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "title": self.title,
            "company": self.company,
            "company_url": self.company_url,
            "location": self.location,
            "tags": self.tags,
            "salary": {
                "min": self.min_salary,
                "max": self.max_salary,
                "currency": "USD",
            }
            if self.min_salary or self.max_salary
            else None,
            "apply_url": self.apply_url,
            "source": self.source,
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
        }


class SourceHealth(Base):
    """Track health of each data source."""

    __tablename__ = "source_health"

    source_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    def __init__(self, **kwargs):
        for field in ("last_success_at", "last_error", "last_run_at", "created_at", "updated_at"):
            if field in kwargs and isinstance(kwargs[field], str):
                kwargs[field] = _coerce_datetime(kwargs[field])
        super().__init__(**kwargs)


class SyncRun(Base):
    """Record of each pipeline sync run."""

    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "ats" or "scrape"
    sources_total: Mapped[int] = mapped_column(Integer, nullable=False)
    sources_succeeded: Mapped[int] = mapped_column(Integer, nullable=False)
    sources_failed: Mapped[int] = mapped_column(Integer, nullable=False)
    sources_disabled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_added: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_expired: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sync_runs_started_at", "started_at"),
    )

    def __init__(self, **kwargs):
        for field in ("started_at", "completed_at"):
            if field in kwargs:
                kwargs[field] = _coerce_datetime(kwargs[field])
        super().__init__(**kwargs)