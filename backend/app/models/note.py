<<<<<<< HEAD
"""Internal counseling note model (E24; Journey J17).

A staff-only comment row attached to a student (and optionally to one
of the student's applications). Authored by a staff user and hidden
from the student — the read/write API in this ticket enforces that
the author is a staff role (counselor / verifier / branch manager /
owner / etc.) and that the student role is blocked at every endpoint.
=======
"""Internal counseling note model (E24 schema; Journey J17).

A staff-only comment thread row attached to a student (and optionally
to one of the student's applications). Authored by a staff user and
hidden from the student — the read/write API and any student-facing
visibility checks land in the sibling E24 task #165; here we only own
the persisted shape.
>>>>>>> origin/main

Design (Requirements §5 "Internal notes: Staff-only comment thread
per student (counselor/verifier/branch manager visible), hidden from
student"; Journey J17 "Counselor logs internal meeting notes"; Epic
E24; ADR-0001):

* Tenant-scoped (ADR-0001: every table carries ``tenant_id``).
  Inherited from :class:`TenantScopedBase`, which also provides
  ``id``, ``created_at``, and ``updated_at``.
* ``student_id`` is the FK to ``users`` (the student the note is
  about). Required because the spec describes notes as a "comment
  thread per student". Combined with tenant scoping this is the
  primary access pattern for the J17 list.
* ``application_id`` is an optional FK to ``applications`` — the
  notes-thread UI sits on the application detail view (E24 frontend
  ticket #166) and staff often want to anchor a note to the specific
  application they are counseling. Nullable so a note can also be
  recorded at the student level (e.g. a general counseling note that
  pre-dates an application).
* ``author_user_id`` is the FK to ``users`` (the staff who wrote the
<<<<<<< HEAD
  note). Required for audit (Requirements §8: "Audit log: basic trail
  on key actions").
* ``body`` is the free-text content of the note (Requirements §5:
  internal comment). ``Text`` with no length cap to allow long-form
  counseling notes.

Role separation (student hidden, staff visible) is enforced at the
router layer (see ``app/routers/notes.py``); the model itself does not
encode the constraint because it would couple the schema to RBAC.
=======
  note: counselor / verifier / branch manager per Requirements §5).
  Required for audit (Requirements §8: "Audit log: basic trail on
  key actions"). The staff/student separation is enforced at the API
  layer in #165; the model itself does not encode that constraint
  because it would couple the schema to RBAC.
* ``body`` is the free-text content of the note (Requirements §5:
  internal comment). ``Text`` with no length cap to allow long-form
  counseling notes.
>>>>>>> origin/main
"""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase

__all__ = ["Note"]


class Note(TenantScopedBase):
    """An internal counseling note attached to a student (E24; Journey J17)."""

    __tablename__ = "notes"

    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    author_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
<<<<<<< HEAD
    body: Mapped[str] = mapped_column(Text, nullable=False)
=======
    body: Mapped[str] = mapped_column(Text, nullable=False)
>>>>>>> origin/main
