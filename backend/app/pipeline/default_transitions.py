"""Platform-default stage transition rules (E25; J18).

Defines the canonical list of platform-default valid transitions and the
idempotent :func:`seed_default_stage_transitions` function used by both
the Alembic migration (``f7a8b9c0d1e2``) and the application startup
hook in :mod:`app.main` so the rule table is populated on every boot,
regardless of whether the schema was created via ``alembic upgrade`` or
``Base.metadata.create_all`` (the latter is used by the Test Agent's
black-box HTTP harness, see ``agents/test_agent.py``).

Traceability:

* Requirements §5 (pipeline stages + optional Loan Processing)
* Journey J18 (Counselor/staff advances an application)
* Epic E25 (Application Stage Progression Engine)
* Epic E38 (Mark Enrolled), E39 (Mark Rejected), E40 (Mark Withdrawn)
* Epic E36/E37 (Loan opt-in / loan status update — the loan loop)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.stage_transition import StageTransition
from app.pipeline.stages import PipelineStage


def _utc_now() -> datetime:
    """Return a timezone-aware UTC ``datetime`` (portable across SQL dialects)."""
    return datetime.now(timezone.utc)


# Canonical platform-default (from, to) transition pairs. Single source of
# truth used by the migration, the runtime seeder, and the tests.
DEFAULT_TRANSITIONS: tuple[tuple[PipelineStage, PipelineStage], ...] = (
    # Normal forward progression
    (PipelineStage.REGISTERED, PipelineStage.COUNSELING),
    (PipelineStage.COUNSELING, PipelineStage.UNIVERSITY_SHORTLISTING),
    (PipelineStage.UNIVERSITY_SHORTLISTING, PipelineStage.APPLICATION_SUBMITTED),
    (PipelineStage.APPLICATION_SUBMITTED, PipelineStage.DOCUMENT_VERIFICATION),
    (PipelineStage.DOCUMENT_VERIFICATION, PipelineStage.OFFER_LETTER),
    (PipelineStage.OFFER_LETTER, PipelineStage.VISA_PROCESSING),
    (PipelineStage.VISA_PROCESSING, PipelineStage.ENROLLED),
    # Loan processing loop (optional, entered from visa_processing, returns to it)
    (PipelineStage.VISA_PROCESSING, PipelineStage.LOAN_PROCESSING),
    (PipelineStage.LOAN_PROCESSING, PipelineStage.VISA_PROCESSING),
    # Terminal states can be reached from every non-terminal stage
    (PipelineStage.REGISTERED, PipelineStage.REJECTED),
    (PipelineStage.REGISTERED, PipelineStage.WITHDRAWN),
    (PipelineStage.COUNSELING, PipelineStage.REJECTED),
    (PipelineStage.COUNSELING, PipelineStage.WITHDRAWN),
    (PipelineStage.UNIVERSITY_SHORTLISTING, PipelineStage.REJECTED),
    (PipelineStage.UNIVERSITY_SHORTLISTING, PipelineStage.WITHDRAWN),
    (PipelineStage.APPLICATION_SUBMITTED, PipelineStage.REJECTED),
    (PipelineStage.APPLICATION_SUBMITTED, PipelineStage.WITHDRAWN),
    (PipelineStage.DOCUMENT_VERIFICATION, PipelineStage.REJECTED),
    (PipelineStage.DOCUMENT_VERIFICATION, PipelineStage.WITHDRAWN),
    (PipelineStage.OFFER_LETTER, PipelineStage.REJECTED),
    (PipelineStage.OFFER_LETTER, PipelineStage.WITHDRAWN),
    (PipelineStage.VISA_PROCESSING, PipelineStage.REJECTED),
    (PipelineStage.VISA_PROCESSING, PipelineStage.WITHDRAWN),
    (PipelineStage.LOAN_PROCESSING, PipelineStage.REJECTED),
    (PipelineStage.LOAN_PROCESSING, PipelineStage.WITHDRAWN),
)


def _build_default_rows() -> list[dict]:
    """Return default rows ready for Core ``insert()`` with timestamps set."""
    now = _utc_now()
    return [
        {
            "from_stage": from_stage,
            "to_stage": to_stage,
            "tenant_id": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        for from_stage, to_stage in DEFAULT_TRANSITIONS
    ]


def seed_default_stage_transitions(db: Session) -> int:
    """Insert the platform-default transition rows that are not yet present.

    This is idempotent: rows are identified by the unique constraint
    ``(from_stage, to_stage, tenant_id)`` and ``tenant_id IS NULL`` for
    platform defaults. Missing rows are inserted; existing rows are left
    untouched so that any tenant-side deactivation (``is_active=False``)
    on a default row is preserved across restarts.

    Uses Python-side ``datetime.now(timezone.utc)`` rather than
    ``sa.func.now()`` so the seeder works identically under SQLite
    (used by tests and the Test Agent's HTTP harness) and PostgreSQL
    (production).

    Returns:
        Number of new rows inserted (0 if the rule table is already seeded).
    """
    table = StageTransition.__table__
    # Query only the platform-default rows (tenant_id IS NULL) for the pairs
    # we care about; this is small and bounded by ``len(DEFAULT_TRANSITIONS)``.
    existing = {
        (row.from_stage, row.to_stage)
        for row in db.query(StageTransition).filter(StageTransition.tenant_id.is_(None)).all()
    }
    to_insert = [
        row
        for row in _build_default_rows()
        if (row["from_stage"], row["to_stage"]) not in existing
    ]
    if to_insert:
        db.execute(table.insert(), to_insert)
        db.commit()
    return len(to_insert)