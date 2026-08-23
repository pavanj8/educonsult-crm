"""Internal counseling notes CRUD endpoints (E24; Journey J17; #165).

Staff-only note thread attached to a student (and optionally to one of
the student's applications). The author and the student are both
``users`` rows — the visibility rule is "staff (counselor / verifier /
branch manager / owner / super admin) see and write, student does not
even know they exist" (Requirements §5 "Internal notes: Staff-only
comment thread per student (counselor/verifier/branch manager visible),
hidden from student").

Permission grants are wired through ``NOTE_READ`` / ``NOTE_CREATE`` /
``NOTE_UPDATE`` / ``NOTE_DELETE`` so the role+permission split is
visible at the OpenAPI layer:

* ``NOTE_READ`` is granted to super admin, consultancy owner, branch
  manager, counselor, document verifier, and receptionist (front-desk
  read-only visibility is appropriate; receptionist does not get
  ``NOTE_CREATE`` because they don't author internal notes — they only
  intake students per Requirements §3).
* ``NOTE_CREATE`` / ``NOTE_UPDATE`` / ``NOTE_DELETE`` are granted to
  super admin, consultancy owner, branch manager, and counselor (the
  roles the spec explicitly calls out as note authors). Note that
  ``NOTE_UPDATE`` / ``NOTE_DELETE`` are NOT granted to document
  verifier or receptionist — every PATCH/DELETE is additionally gated
  on ``author_user_id == current_user.id`` so only the original author
  can edit/delete. Splitting create from update/delete at the
  permission layer means a future ticket that wants to grant branch
  managers the right to edit a counselor's note can grant
  ``NOTE_UPDATE`` to a new role without weakening the
  create-vs-edit distinction (security analyst finding on iteration
  #1).
* The student role is not granted any note permission, which is how
  the "hidden from student" requirement is enforced at the dependency
  layer.

Branch scoping follows ADR-0004 + the rest of the counseling domain
(``apply_tenant_scope`` + manual JOIN through ``User.branch_id`` since
``Note`` is not branch-scoped at the schema level — see the
"_BRANCH_SCOPED_NOTE_ROLES" frozenset below):

* Super Admin: platform-wide, unfiltered.
* Consultancy Owner: tenant-wide, unfiltered by branch.
* Branch Manager / Counselor: tenant + branch scoped; counselors are
  additionally restricted to notes for students they are the assigned
  counselor on (mirrors ``GET /applications/assigned-to-me`` from E21).
* Document Verifier / Receptionist: tenant scoped only (they are
  present in every branch and the role-switch no longer special-cases
  them with a "no further branch filter" comment — there is no
  unreachable verifier/receptionist branch in this module; the
  frozenset at module top is the single source of truth, mirroring
  ``_CROSS_BRANCH_ROLES`` in ``app/db/branch_scope.py``).
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
_AUTHOR_ONLY_EDIT_DETAIL = "Only the note's author may edit it"
_AUTHOR_ONLY_DELETE_DETAIL = "Only the note's author may delete it"

# Roles whose notes view must be filtered to the caller's branch (ADR-0004).
# Single source of truth for "who is branch-scoped on /notes", mirroring the
# frozenset convention used in ``app/db/branch_scope.py``. Keep this list in
# lock-step with ``_BRANCH_SCOPED_ROLES`` in tests/db/test_access_denial_matrix.py
# and with any future role that needs branch-scoped note visibility.
#
# The complementary set is ``_CROSS_BRANCH_ROLES`` in ``app/db/branch_scope.py``
# (super admin + consultancy owner are platform/tenant-wide). Every other role
# (counselor, branch manager, document verifier, receptionist, visa processor,
# student) is intended to be either branch-scoped on /notes or excluded from
# the endpoint entirely by the ``NOTE_READ`` permission grant — so this
# frozenset currently lists only the two roles that are scoped at the
# branch level here, while verifier/receptionist/visa_processor are NOT
# scoped at the branch level on /notes because they are tenant-wide
# read-only staff (mirrors how meetings.py handles them). Adding a new
# branch-scoped role on /notes requires updating both this frozenset and
# the matching set in ``app/db/branch_scope.py`` so the role policy
# stays canonical (software architect finding on iteration #1).
_BRANCH_SCOPED_NOTE_ROLES = frozenset({Role.BRANCH_MANAGER, Role.COUNSELOR})


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
    """Load the student User row, enforcing tenant scope and student role.

    Returns 404 for:

    * a row that does not exist,
    * a cross-tenant row (skipping the tenant check for super admins,
      who are platform-wide by design),
    * a row whose role is not ``STUDENT`` (e.g. the caller probes a
      ``users`` id that resolves to a non-student row).

    The 404 collapses the "missing row" and "wrong-role row" failure
    modes into a single, indistinguishable response so a probe cannot
    enumerate non-student user ids by status-code differential
    (security analyst finding on iteration #1).
    """
    try:
        student = db.get(User, student_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if student is None or student.role != Role.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_STUDENT_NOT_FOUND_DETAIL,
        )

    # Super admins are platform-wide and have tenant_id=None by design.
    if user.role != Role.SUPER_ADMIN and student.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
    db: Session,
    user: AuthenticatedUser,
    student: User,
    *,
    enforce_assigned: bool = True,
) -> None:
    """Branch-scope a single student for branch-scoped note roles.

    Roles not in ``_BRANCH_SCOPED_NOTE_ROLES`` (super admin, consultancy
    owner, document verifier, receptionist, visa processor, student)
    bypass this guard — super admin and consultancy owner are
    platform/tenant-wide by design, and verifier/receptionist are
    present in every branch (no branch filter applies to them in the
    list endpoint either; the canonical scope helper ``apply_branch_scope``
    would block them with a ``BranchScopeError`` because they lack
    branch_id, which is the wrong outcome for notes).

    Counselors are further restricted to students they are currently
    the assigned counselor on (i.e. there exists at least one
    ``Application`` row for the student in the caller's branch with
    ``assigned_counselor_id == caller.id``). The ``enforce_assigned``
    flag (default ``True``) lets callers that already know the
    caller's role is branch manager (e.g. the list endpoint's branch
    manager probe path) skip the counselor-specific check; passing
    ``enforce_assigned=False`` is a no-op for non-counselor callers
    because they have no assigned-counselor constraint to apply. This
    matches the counselor's "assigned-to-me" application queue shape
    (J14) and is the same authorization model the meetings router
    uses for counselors in E22.

    The note ``Note`` schema has no ``branch_id`` column (notes are
    student-anchored), so the canonical ``apply_branch_scope`` helper
    in ``app/db/branch_scope.py`` cannot apply directly — that helper
    expects ``model.branch_id`` on the queried model. Instead, branch
    scoping for ``Note`` is enforced via a JOIN through ``User`` on
    ``Note.student_id`` (see :func:`_scoped_notes_query`) and on the
    per-note path via this helper, which checks the student's
    ``branch_id``. Keep both code paths in sync if branch-scoping
    rules ever change (software architect finding on iteration #1).
    """
    if user.role not in _BRANCH_SCOPED_NOTE_ROLES:
        return

    if user.branch_id is None or student.branch_id != user.branch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_BRANCH_ACCESS_DENIED_DETAIL,
        )

    if enforce_assigned and user.role == Role.COUNSELOR:
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


def _scoped_notes_query(
    db: Session, user: AuthenticatedUser
) -> Select[tuple[Note]]:
    """Return a tenant + branch-scoped SELECT on ``Note``.

    * Super Admin: unfiltered (platform-wide).
    * Consultancy Owner: tenant-scoped, all branches.
    * Branch Manager: tenant + branch scoped (joined through
      ``User.branch_id`` since ``Note`` has no branch column).
    * Counselor: tenant + branch scoped, AND restricted to notes for
      students they are the assigned counselor on.
    * Document Verifier / Receptionist / Visa Processor: tenant scoped
      only (no branch filter — they are present in every branch).
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

    # Super admins are platform-wide with ``tenant_id=None``; their
    # note query is unfiltered by tenant. Non-super-admin callers
    # require a tenant match.
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOTE_NOT_FOUND_DETAIL,
        )
    if (
        user.role != Role.SUPER_ADMIN
        and note.tenant_id != user.tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOTE_NOT_FOUND_DETAIL,
        )

    try:
        student = db.get(User, note.student_id)
    except OperationalError as exc:
        _handle_db_error(exc, rollback=False)

    if student is None:
        # The student FK is ON DELETE CASCADE; treat a dangling FK
        # as a not-found note rather than leaking internals.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_NOTE_NOT_FOUND_DETAIL,
        )
    if (
        user.role != Role.SUPER_ADMIN
        and student.tenant_id != user.tenant_id
    ):
        # A super admin can read notes for any tenant; a tenant-scoped
        # caller must match the student's tenant.
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
    # Only ``current_user.id`` is the genuine precondition for create
    # (we need to know who the author is). ``tenant_id`` may legitimately
    # be ``None`` for super admins (platform-wide role); we derive the
    # note's ``tenant_id`` from the student in that case so the row
    # satisfies the NOT NULL constraint while still letting the
    # platform-wide role author on any tenant.
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    student = _load_student(db, current_user, payload.student_id)

    if payload.application_id is not None:
        _load_application(
            db, current_user, payload.application_id, payload.student_id
        )

    _enforce_branch_scope_on_student(db, current_user, student)

    note_tenant_id = (
        current_user.tenant_id
        if current_user.tenant_id is not None
        else student.tenant_id
    )

    now = _utc_now()
    note = Note(
        tenant_id=note_tenant_id,
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

    Newest-first ordering (``Note.created_at DESC``) matches how the
    notes-thread UI renders the conversation — a chat-style thread is
    read top-to-bottom with the most recent message first, mirroring
    the consumer expectation rather than forcing the frontend to
    reverse the list client-side (UX architect finding on iteration
    #1).
    """
    # Super admins are platform-wide with ``tenant_id=None`` by design;
    # :func:`_scoped_notes_query` short-circuits to the unfiltered
    # SELECT in that case. We do NOT raise here so the platform-wide
    # role can list platform-wide.

    try:
        statement = _scoped_notes_query(db, current_user)

        # If the caller is branch-scoped and supplies ``student_id``, we
        # reject the request rather than silently returning ``[]``: a
        # branch-scoped user that probes another branch's student id
        # should not be able to distinguish "no notes exist for this
        # student" from "the student is out of scope". The single-note
        # GET endpoint already returns 403 for the same probe via
        # :func:`_load_note`; the list endpoint mirrors that for
        # consistency (senior developer finding on iteration #1).
        if student_id is not None and current_user.role in (
            Role.BRANCH_MANAGER,
            Role.COUNSELOR,
        ):
            try:
                student = db.get(User, student_id)
            except OperationalError as exc:
                _handle_db_error(exc, rollback=False)
            if (
                student is None
                or student.tenant_id != current_user.tenant_id
                or student.role != Role.STUDENT
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_BRANCH_ACCESS_DENIED_DETAIL,
                )
            # Reuse the same helper as the per-note path so the
            # branch-match (and counselor-assigned-to-student) rules
            # stay in one place. Branch managers do not have an
            # assigned-counselor constraint, so we explicitly disable
            # the counselor-specific check for that role
            # (``enforce_assigned=False`` is a no-op for non-counselor
            # callers — only counselors have the assigned-to-student
            # constraint to apply).
            _enforce_branch_scope_on_student(
                db,
                current_user,
                student,
                enforce_assigned=(current_user.role == Role.COUNSELOR),
            )

        if student_id is not None:
            statement = statement.where(Note.student_id == student_id)
        if application_id is not None:
            statement = statement.where(Note.application_id == application_id)

        # Newest-first: chat-style notes thread reads top-to-bottom.
        statement = statement.order_by(Note.created_at.desc(), Note.id.desc())
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
    return _load_note(db, note_id, current_user)


@router.patch("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int,
    payload: NoteUpdate,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.NOTE_UPDATE)),
    ],
    db: Session = Depends(get_db),
) -> Note:
    """Update a note's body (J17).

    Two-layer authorization:

    * The dependency on ``NOTE_UPDATE`` rejects callers whose role
      does not have edit privileges (e.g. document verifier /
      receptionist have ``NOTE_READ`` but not ``NOTE_UPDATE``).
    * After the note is loaded with full tenant + branch scoping,
      an inline ``author_user_id == current_user.id`` check enforces
      "only the author may edit". A future ticket that wants to grant
      branch managers edit-on-behalf-of-counselor can grant
      ``NOTE_UPDATE`` to the branch manager role *and* relax (or
      replace) the inline check; the OpenAPI contract now exposes the
      role distinction at the dependency layer.
    """
    # Super admins are platform-wide with ``tenant_id=None`` by
    # design; the role is the platform-wide author and may edit any
    # note they authored. We only require ``current_user.id`` so the
    # author-only check below has a comparison value.
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    note = _load_note(db, note_id, current_user)
    if note.author_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_AUTHOR_ONLY_EDIT_DETAIL,
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
        Depends(require_permission(Permission.NOTE_DELETE)),
    ],
    db: Session = Depends(get_db),
) -> None:
    """Delete a note (J17).

    Two-layer authorization, mirroring :func:`update_note`:

    * ``NOTE_DELETE`` dependency rejects callers whose role does not
      have delete privileges (e.g. document verifier / receptionist).
    * Inline ``author_user_id == current_user.id`` check enforces
      "only the author may delete" (Requirements §8 audit trail:
      letting a peer silently remove another staff's note would break
      the audit trail).
    """
    # Super admins are platform-wide with ``tenant_id=None`` by
    # design; the role is the platform-wide author and may delete any
    # note they authored. We only require ``current_user.id`` so the
    # author-only check below has a comparison value.
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    note = _load_note(db, note_id, current_user)
    if note.author_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_AUTHOR_ONLY_DELETE_DETAIL,
        )

    db.delete(note)
    try:
        db.commit()
    except OperationalError as exc:
        _handle_db_error(exc, rollback=True, db=db)
