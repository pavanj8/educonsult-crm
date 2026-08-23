"""Internal counseling notes CRUD endpoints (E24; Journey J17; #165).

Staff-only note thread attached to a student (and optionally to one of
the student's applications). The author and the student are both
``users`` rows — the visibility rule is "staff (counselor / verifier /
branch manager / owner / super admin) see and write, student does not
even know they exist" (Requirements §5 "Internal notes: Staff-only
comment thread per student (counselor/verifier/branch manager visible),
hidden from student").

Permission grants are wired through ``NOTE_READ`` and ``NOTE_CREATE``:

* ``NOTE_READ`` is granted to consultancy owner, branch manager,
  counselor, document verifier, and receptionist (front-desk
  read-only visibility is appropriate; receptionist does not get
  ``NOTE_CREATE`` because they don't author internal notes — they
  only intake students per Requirements §3).
* ``NOTE_CREATE`` is granted to consultancy owner, branch manager,
  and counselor (the three roles the spec explicitly calls out as
  note authors).
* The student role is not granted either permission, which is how the
  "hidden from student" requirement is enforced at the dependency
  layer.

Branch scoping follows ADR-0004 + the rest of the counseling domain
(``apply_tenant_scope`` + ``apply_branch_scope``):

* Super Admin: platform-wide, unfiltered.
* Consultancy Owner: tenant-wide, unfiltered by branch.
* Branch Manager / Counselor: tenant + branch scoped.
* Document Verifier / Receptionist: tenant scoped; ``apply_branch_scope``
  is not applied because they are not branch-scoped roles per ADR-0004
  (verifier and receptionist are present in every branch).

Counselors are additionally restricted to notes whose student they are
currently the assigned counselor on (i.e. at least one ``Application``
row for that student in the counselor's branch has
``assigned_counselor_id == counselor.id``). This mirrors the
``GET /applications/assigned-to-me`` shape and prevents a counselor
from peeking at notes for students they aren't assigned to.
"""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, and_, exists, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.branch_scope import BranchScopeError
from app.db.database import get_db
from app.db.tenant_scope import TenantScopeError, apply_tenant_scope
from app.models.application import Application
from app.models.note import Note
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate

router = APIRouter(prefix="/notes", tags=["notes"])

_DB_UNAVAILABLE_DETAIL = "Notes service is temporarily unavailable"
_NOTE_NOT_FOUND_DETAIL = "Note not found"
_STUDENT_NOT_FOUND_DETAIL = "Student not found"
_APPLICATION_NOT_FOUND_DETAIL = "Application not found"
_STUDENT_MISMATCH_DETAIL = "Application is not for the named student"
_BRANCH_ACCESS_DENIED_DETAIL = "User has no access to this resource"
_COUNSELOR_NOT_ASSIGNED_DETAIL = (
    "Counselor is not assigned to this student; cannot view notes"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _handle_db_error(
    exc: OperationalError, *, rollback: bool, db: Session | None = None
) -> None:
    """Convert an :class:`OperationalError` into a 503 HTTPException.

    ``rollback=True`` performs ``db.rollback()`` before raising so the
    session is left in a usable state for the next request; the read-only
    path passes ``rollback=False`` (no pending mutations to roll back).
    Centralizing the message keeps the 4x ``try/except
    OperationalError -> 503`` boilerplate out of each handler.
    """
    if rollback and db is not None:
        db.rollback()
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=_DB_UNAVAILABLE_DETAIL,
    ) from exc


def _load_student(db: Session, user: AuthenticatedUser, student_id: int) -> User:
    """Load the student User row, enforcing tenant scope (404 for cross-tenant)."""
    try:
        student = db.get(User, student_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if student is None or student.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_STUDENT_NOT_FOUND_DETAIL,
        )

    if student.role != Role.STUDENT:
        # The note spec is "comment thread per student" -- a note
        # about a non-student user is meaningless. Refuse early so the
        # caller gets a useful error rather than an FK violation.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_STUDENT_NOT_FOUND_DETAIL,
        )

    return student


def _load_application(
    db: Session, user: AuthenticatedUser, application_id: int, student_id: int
) -> Application:
    """Load an application, enforcing tenant scope and student match.

    Used by create when ``application_id`` is supplied. Returns 404 for
    cross-tenant or missing applications, 422 if the application is for
    a different student than the note's anchor.
    """
    try:
        application = db.get(Application, application_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if application is None or application.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_APPLICATION_NOT_FOUND_DETAIL,
        )

    if application.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_STUDENT_MISMATCH_DETAIL,
        )

    return application


def _enforce_branch_scope_on_student(
    db: Session, user: AuthenticatedUser, student: User
) -> None:
    """Branch-scope a single student for branch-scoped staff roles.

    Counselors are further restricted to students they are currently
    the assigned counselor on (i.e. there exists at least one
    ``Application`` row for the student in the caller's branch with
    ``assigned_counselor_id == caller.id``). This matches the
    counselor's "assigned-to-me" application queue shape (J14) and
    is the same authorization model the meetings router uses for
    counselors in E22.
    """
    if user.role in (Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER):
        return

    if user.role == Role.BRANCH_MANAGER:
        if user.branch_id is None or student.branch_id != user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_BRANCH_ACCESS_DENIED_DETAIL,
            )
        return

    if user.role == Role.COUNSELOR:
        if user.branch_id is None or student.branch_id != user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_BRANCH_ACCESS_DENIED_DETAIL,
            )
        # Counselors must be the assigned counselor on at least one
        # of the student's applications in this branch. We check via
        # the SQLAlchemy ``exists()`` subquery against ``Application``
        # rather than loading all of the student's apps into Python.
        try:
            assigned_exists = db.execute(
                select(
                    exists().where(
                        and_(
                            Application.student_id == student.id,
                            Application.assigned_counselor_id == user.id,
                            Application.branch_id == user.branch_id,
                        )
                    )
                )
            ).scalar_one()
        except OperationalError as exc:
            _handle_db_error(exc, rollback=False)
        if not assigned_exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_COUNSELOR_NOT_ASSIGNED_DETAIL,
            )
        return

    # Document Verifier / Receptionist / others with NOTE_READ: tenant
    # scope is already enforced above; no further branch filter applies
    # (they are present in every branch).


def _scoped_notes_query(
    db: Session, user: AuthenticatedUser
) -> Select[tuple[Note]]:
    """Return a tenant + branch-scoped SELECT on ``Note``.

    * Super Admin: unfiltered (platform-wide).
    * Consultancy Owner: tenant-scoped, all branches.
    * Branch Manager: tenant + branch scoped.
    * Document Verifier / Receptionist: tenant scoped (no branch filter,
      they are present in every branch).
    * Counselor: tenant + branch scoped, AND restricted to notes for
      students they are the assigned counselor on.
    """
    statement: Select[tuple[Note]] = apply_tenant_scope(select(Note), Note, user)

    if user.role == Role.BRANCH_MANAGER:
        # Notes are student-anchored; branch-scope via the student's
        # branch_id (notes themselves do not carry branch_id -- they
        # are tenant-scoped only).
        if user.branch_id is None:
            raise BranchScopeError(
                f"User with role {user.role.value} requires branch_id"
            )
        statement = statement.join(
            User, User.id == Note.student_id
        ).where(User.branch_id == user.branch_id)
        return statement

    if user.role == Role.COUNSELOR:
        if user.branch_id is None:
            raise BranchScopeError(
                f"User with role {user.role.value} requires branch_id"
            )
        statement = statement.join(
            User, User.id == Note.student_id
        ).where(
            User.branch_id == user.branch_id,
        )
        # Restrict to students the counselor is the assigned counselor on.
        statement = statement.where(
            exists().where(
                and_(
                    Application.student_id == Note.student_id,
                    Application.assigned_counselor_id == user.id,
                    Application.branch_id == user.branch_id,
                )
            )
        )
        return statement

    return statement


def _load_note(
    db: Session, note_id: int, user: AuthenticatedUser
) -> Note:
    """Load a single note with full tenant + branch + role scoping.

    Used by GET / PATCH / DELETE so the same authorization model
    applies to every per-note endpoint.
    """
    try:
        note = db.get(Note, note_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if note is None or note.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOTE_NOT_FOUND_DETAIL,
        )

    try:
        student = db.get(User, note.student_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if student is None or student.tenant_id != user.tenant_id:
        # The student FK is ON DELETE CASCADE; treat a dangling FK
        # as a not-found note rather than leaking internals.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOTE_NOT_FOUND_DETAIL,
        )

    _enforce_branch_scope_on_student(db, user, student)
    return note


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreate,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTE_CREATE)),
    ],
    db: Session = Depends(get_db),
) -> Note:
    """Create a new internal counseling note (J17).

    Author is always the caller (``author_user_id = current_user.id``).
    The student and (optional) application anchors are validated for
    tenant scope and student/application consistency. Branch-scoped
    staff (counselor / branch manager) must be in the student's branch;
    counselors must additionally be the assigned counselor on at least
    one of the student's applications.
    """
    if current_user.tenant_id is None or current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    student = _load_student(db, current_user, payload.student_id)

    if payload.application_id is not None:
        application = _load_application(
            db, current_user, payload.application_id, payload.student_id
        )
        # Branch scope on the application matches the student's branch
        # in practice (the application's branch_id mirrors the student's
        # at creation time), but we re-check explicitly so a future
        # ticket that decouples student.branch_id from application.branch_id
        # does not silently break this.
        if (
            current_user.role not in (Role.SUPER_ADMIN, Role.CONSULTANCY_OWNER)
            and current_user.branch_id is not None
            and application.branch_id != current_user.branch_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_BRANCH_ACCESS_DENIED_DETAIL,
            )
    else:
        application = None

    _enforce_branch_scope_on_student(db, current_user, student)

    now = _utc_now()
    note = Note(
        tenant_id=current_user.tenant_id,
        student_id=payload.student_id,
        application_id=payload.application_id,
        author_user_id=current_user.id,
        body=payload.body,
        created_at=now,
        updated_at=now,
    )
    db.add(note)
    try:
        db.commit()
    except OperationalError as exc:
        _handle_db_error(exc, rollback=True, db=db)

    db.refresh(note)
    return note


@router.get("", response_model=list[NoteResponse])
def list_notes(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTE_READ)),
    ],
    db: Session = Depends(get_db),
    student_id: int | None = Query(default=None, gt=0),
    application_id: int | None = Query(default=None, gt=0),
) -> list[Note]:
    """List internal counseling notes visible to the caller (J17).

    Tenant + branch + role scoping is applied through
    :func:`_scoped_notes_query`. Optional filters narrow the list by
    ``student_id`` or ``application_id`` for the notes-thread UI
    (E24 frontend ticket #166).
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    try:
        statement = _scoped_notes_query(db, current_user)

        # If the caller is branch-scoped and supplies student_id, the
        # student must be in the caller's branch (and a counselor must
        # be assigned to them). This catches a "probe" attempt where a
        # branch-scoped user guesses another branch's student id.
        if student_id is not None and current_user.role in (
            Role.BRANCH_MANAGER,
            Role.COUNSELOR,
        ):
            try:
                student = db.get(User, student_id)
            except OperationalError as exc:
                _handle_db_error(exc, rollback=False)
            if student is None or student.tenant_id != current_user.tenant_id:
                # Treat unknown / cross-tenant student as a hard not-found
                # so the response shape is predictable.
                return []
            if (
                student.branch_id is None
                or current_user.branch_id is None
                or student.branch_id != current_user.branch_id
            ):
                return []
            if current_user.role == Role.COUNSELOR:
                _enforce_branch_scope_on_student(db, current_user, student)

        if student_id is not None:
            statement = statement.where(Note.student_id == student_id)
        if application_id is not None:
            statement = statement.where(Note.application_id == application_id)

        statement = statement.order_by(Note.created_at)
        return list(db.scalars(statement).all())
    except (TenantScopeError, BranchScopeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(
    note_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTE_READ)),
    ],
    db: Session = Depends(get_db),
) -> Note:
    """Fetch a single note by id (J17)."""
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return _load_note(db, note_id, current_user)


@router.patch("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int,
    payload: NoteUpdate,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTE_CREATE)),
    ],
    db: Session = Depends(get_db),
) -> Note:
    """Update a note's body (J17).

    Only the author of the note may edit it; the spec describes notes
    as a per-author "comment" and Requirements §8 audit trail integrity
    means we must not silently rewrite another staff member's note.
    Tenant + branch + role scoping is enforced in :func:`_load_note`.
    """
    if current_user.tenant_id is None or current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    note = _load_note(db, note_id, current_user)
    if note.author_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note's author may edit it",
        )

    note.body = payload.body
    note.updated_at = _utc_now()
    try:
        db.commit()
    except OperationalError as exc:
        _handle_db_error(exc, rollback=True, db=db)

    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTE_CREATE)),
    ],
    db: Session = Depends(get_db),
) -> None:
    """Delete a note (J17).

    Only the author of the note may delete it. The spec describes a
    comment thread per student where the staff are the authors; letting
    a peer silently remove another staff's note would break the audit
    trail (Requirements §8). Tenant + branch + role scoping is enforced
    in :func:`_load_note`.
    """
    if current_user.tenant_id is None or current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    note = _load_note(db, note_id, current_user)
    if note.author_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note's author may delete it",
        )

    db.delete(note)
    try:
        db.commit()
    except OperationalError as exc:
        _handle_db_error(exc, rollback=True, db=db)
