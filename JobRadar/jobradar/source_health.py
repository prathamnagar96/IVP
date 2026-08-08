"""Source health tracking utilities (re-exports from db.client)."""

from jobradar.db.client import DatabaseClient

# Re-export for convenience
__all__ = ["DatabaseClient"]