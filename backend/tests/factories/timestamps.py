from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for model created_at/updated_at fields."""
    return datetime.now(timezone.utc)
