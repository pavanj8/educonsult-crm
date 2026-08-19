"""Monotonic ID generator for test fixtures."""

_id_counter = 0


def reset_test_ids(start: int = 1) -> None:
    """Reset the shared test ID sequence (call from tests that need deterministic IDs)."""
    global _id_counter
    _id_counter = start - 1


def next_test_id() -> int:
    """Return the next integer ID for test entities."""
    global _id_counter
    _id_counter += 1
    return _id_counter
