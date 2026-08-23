"""Meeting test helpers (E22; Journey J15).

Helpers for the ``/meetings`` schedule/list/update router tests: tenant +
branch seeding, user factories, and a ``seed_meeting`` builder so each
test can compose just the rows it needs.
"""

from datetime import datetime, timedelta, timezone

from app.models.meeting import Meeting
from app.models.tenant import Tenant


def _create_tenant(db_session, *, name: str = "EduConsult Test", slug: str = "educonsult") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def seed_meeting(
    db_session,
    *,
    tenant_id: int,
    application_id: int,
    student_id: int,
    counselor_id: int,
    scheduled_at: datetime | None = None,
    duration_minutes: int = 45,
    location: str | None = None,
    notes: str | None = None,
) -> Meeting:
    """Insert and return a Meeting row with stable defaults."""
    now = scheduled_at or datetime.now(timezone.utc) + timedelta(days=1)
    meeting = Meeting(
        tenant_id=tenant_id,
        application_id=application_id,
        student_id=student_id,
        counselor_id=counselor_id,
        scheduled_at=now,
        duration_minutes=duration_minutes,
        location=location,
        notes=notes,
        created_at=now,
        updated_at=now,
    )
    db_session.add(meeting)
    db_session.commit()
    db_session.refresh(meeting)
    return meeting
