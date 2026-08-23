"""Note test helpers (E24; Journey J17).

Helpers for the ``/notes`` CRUD router tests: tenant + branch seeding,
user factories, and a ``seed_note`` builder so each test can compose
just the rows it needs.
"""

from datetime import datetime, timezone

from app.models.note import Note
from app.models.tenant import Tenant


def create_tenant(
    db_session, *, name: str = "EduConsult Test", slug: str = "educonsult"
) -> Tenant:
    """Insert and return a Tenant row.

    Public helper — the ``/notes`` test module imports it directly so
    the tenant bootstrap is the single source of truth across the
    counseling-domain test suite (software architect finding on
    iteration #3).
    """
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def seed_note(
    db_session,
    *,
    tenant_id: int,
    student_id: int,
    author_user_id: int,
    body: str = "Counseling note body",
    application_id: int | None = None,
    created_at: datetime | None = None,
) -> Note:
    """Insert and return a Note row with stable defaults."""
    now = created_at or datetime.now(timezone.utc)
    note = Note(
        tenant_id=tenant_id,
        student_id=student_id,
        application_id=application_id,
        author_user_id=author_user_id,
        body=body,
        created_at=now,
        updated_at=now,
    )
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    return note
