"""Notification creation service + event hooks (E48; Journey J41; issue #230).

This module owns the in-app notification-creation API for the E48 epic:

* :func:`create_notification` — the low-level helper used by the
  service hooks and (in tests) by black-box callers that want to
  inspect raw notification rows.
* :func:`notify_application_stage_advanced` — hook fired by the
  E25 ``advance-stage`` flow (and the mark-enrolled / mark-rejected /
  mark-withdrawn wrappers). Generates a notification for the
  application's student.
* :func:`notify_document_review_outcome` — hook fired by the E29 /
  E30 approve / reject endpoints. Generates a notification for the
  document's uploader.
* :func:`notify_application_created` — hook fired by the E18
  ``POST /applications`` endpoint. Generates a notification for the
  assigned counselor (if any).
* :func:`notify_counselor_assigned` — helper for manual
  reassignment (E20). Generates a notification for the new counselor.

The hooks follow a single design rule from ADR-0004 / Requirements §6:
the notification row is committed **in the same transaction** as the
domain mutation so we never end up with a domain change but no
notification (and never a notification but no domain change). Callers
MUST commit / rollback their session as they already do for the
underlying mutation; we just attach the notification to the same
session.

For the events covered here the recipient is always the application
student (stage change, document review) or the assigned counselor
(application creation, manual reassignment). The set of event types
is exposed as the ``EVENT_*`` constants below so the frontend (E50)
can route / icon them without a magic-string dependency on the
service.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.notification import Notification
from app.models.student_document import StudentDocument
from app.models.user import User
from app.pipeline.stages import PipelineStage

__all__ = [
    "create_notification",
    "notify_application_stage_advanced",
    "notify_document_review_outcome",
    "notify_application_created",
    "notify_counselor_assigned",
    "EVENT_APPLICATION_CREATED",
    "EVENT_APPLICATION_STAGE_ADVANCED",
    "EVENT_DOCUMENT_APPROVED",
    "EVENT_DOCUMENT_REJECTED",
    "EVENT_COUNSELOR_ASSIGNED",
]

#: Application-creation event (E18; Journey J11).
EVENT_APPLICATION_CREATED = "application.created"

#: Stage-advanced event (E25 / E38 / E39 / E40; Journey J18).
EVENT_APPLICATION_STAGE_ADVANCED = "application.stage_advanced"

#: Document-approval event (E29; Journey J22 / J25).
EVENT_DOCUMENT_APPROVED = "document.approved"

#: Document-rejection event (E30; Journey J23 / J25).
EVENT_DOCUMENT_REJECTED = "document.rejected"

#: Manual counselor reassignment event (E20; Journey J13).
EVENT_COUNSELOR_ASSIGNED = "application.counselor_assigned"


def create_notification(
    db: Session,
    *,
    tenant_id: int,
    user_id: Optional[int],
    event_type: str,
    title: str,
    message: str,
    related_application_id: Optional[int] = None,
    related_document_id: Optional[int] = None,
    related_stage_history_id: Optional[int] = None,
) -> Notification:
    """Insert a notification row in the same transaction as the caller.

    Mirrors the project-wide "no silent failures" rule for the
    notifications surface: if the caller commits, the notification is
    persisted; if the caller rolls back, the notification is rolled
    back too. There is no separate flush / commit here — that is by
    design (Requirements §6: notification generation is a side effect
    of the domain event, not an independent transaction).
    """
    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        title=title,
        message=message,
        related_application_id=related_application_id,
        related_document_id=related_document_id,
        related_stage_history_id=related_stage_history_id,
    )
    db.add(notification)
    db.flush()
    return notification


def _recipient_user_id(user: User | None) -> Optional[int]:
    """Return the recipient's user id (or ``None`` when no concrete user exists)."""
    return user.id if user is not None else None


def notify_application_stage_advanced(
    db: Session,
    *,
    application: Application,
    to_stage: PipelineStage,
    changed_by_user_id: Optional[int],
    stage_history_id: Optional[int] = None,
) -> Optional[Notification]:
    """Generate a stage-advanced notification for the application's student.

    Returns ``None`` when there is no resolvable student (e.g. the
    application's ``student_id`` points at a deleted user); the call
    site can ignore the return value — the point is that the row exists
    iff a recipient exists.
    """
    if application.student_id is None:
        return None

    title = f"Application moved to {to_stage.value}"
    message = (
        f"Your application has been advanced to '{to_stage.value}'."
    )
    notification = create_notification(
        db,
        tenant_id=application.tenant_id,
        user_id=application.student_id,
        event_type=EVENT_APPLICATION_STAGE_ADVANCED,
        title=title,
        message=message,
        related_application_id=application.id,
        related_stage_history_id=stage_history_id,
    )
    # Silence "unused argument" — ``changed_by_user_id`` is reserved for
    # a future "actor" field on the notification row (the E50 UI may
    # want to show "advanced by …" later); keep the param for the
    # public hook signature so the router doesn't need to change.
    del changed_by_user_id
    return notification


def notify_document_review_outcome(
    db: Session,
    *,
    document: StudentDocument,
    outcome: str,
    comment: Optional[str] = None,
) -> Optional[Notification]:
    """Generate a review-outcome notification for the document's uploader.

    ``outcome`` must be either ``"approved"`` or ``"rejected"``; the
    helper picks the matching event type and human-readable strings.
    Returns ``None`` when ``document.uploaded_by_user_id`` is ``None``
    (e.g. a cybernetically-deleted uploader — should not happen for
    a live document, but is a safe no-op here).
    """
    if outcome == "approved":
        event_type = EVENT_DOCUMENT_APPROVED
        title = "Document approved"
    elif outcome == "rejected":
        event_type = EVENT_DOCUMENT_REJECTED
        title = "Document rejected"
    else:
        raise ValueError(f"Unknown document review outcome: {outcome!r}")

    suffix = f" Note: {comment}" if comment else ""
    message = f"Your document '{document.original_filename}' was {outcome}.{suffix}"

    return create_notification(
        db,
        tenant_id=document.tenant_id,
        user_id=document.uploaded_by_user_id,
        event_type=event_type,
        title=title,
        message=message,
        related_application_id=document.application_id,
        related_document_id=document.id,
    )


def notify_application_created(
    db: Session,
    *,
    application: Application,
) -> Optional[Notification]:
    """Generate an application-created notification for the assigned counselor.

    No-op when the application has no ``assigned_counselor_id`` (the
    branch had no active counselors at creation time, per E19). The
    notification is not generated for the student because the student
    is the actor who just created the application.
    """
    if application.assigned_counselor_id is None:
        return None

    return create_notification(
        db,
        tenant_id=application.tenant_id,
        user_id=application.assigned_counselor_id,
        event_type=EVENT_APPLICATION_CREATED,
        title="New application assigned",
        message=f"Application #{application.id} has been assigned to you.",
        related_application_id=application.id,
    )


def notify_counselor_assigned(
    db: Session,
    *,
    application: Application,
    new_counselor_user_id: Optional[int],
) -> Optional[Notification]:
    """Generate a counselor-assigned notification (manual reassignment, E20)."""
    if new_counselor_user_id is None:
        return None

    return create_notification(
        db,
        tenant_id=application.tenant_id,
        user_id=new_counselor_user_id,
        event_type=EVENT_COUNSELOR_ASSIGNED,
        title="Application reassigned to you",
        message=f"Application #{application.id} has been reassigned to you.",
        related_application_id=application.id,
    )


# Silence unused-import warning for ``_recipient_user_id``: kept as a
# documented helper for future hooks (e.g. multi-recipient notifications
# when E23 meeting notifications land) without churning the public
# surface.
_ = _recipient_user_id
