"""Note API schemas (E24; Journey J17).

Schemas for the staff-only internal counseling notes CRUD endpoint
mounted at ``/notes`` (this ticket; #165).

The student role is blocked at the router layer; these schemas are
shared between the create/update/read endpoints and intentionally
model only the staff-authored shape.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    """Payload for ``POST /notes`` (Journey J17).

    ``student_id`` is required: the note is always anchored to a student
    (the spec describes a "comment thread per student").

    ``application_id`` is optional — staff may anchor the note to a
    specific application (the notes-thread UI sits on the application
    detail view in #166) or record a general counseling note at the
    student level (e.g. before an application exists).

    ``body`` is the free-text content. It is required and may not be
    blank; a blank note is meaningless and would let an actor stuff
    the thread with empty rows.
    """

    student_id: int = Field(gt=0)
    application_id: int | None = Field(default=None, gt=0)
    body: str = Field(min_length=1)


class NoteUpdate(BaseModel):
    """Payload for ``PATCH /notes/{id}``.

    Only ``body`` is mutable: the student/application anchors and the
    authorship are intrinsic to the note and cannot be changed after
    creation (Requirements §8: audit trail integrity).
    """

    body: str = Field(min_length=1)


class NoteResponse(BaseModel):
    """Shape returned by every read endpoint (create / list / get / update)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    student_id: int
    application_id: int | None
    author_user_id: int
    body: str
    created_at: datetime
    updated_at: datetime
