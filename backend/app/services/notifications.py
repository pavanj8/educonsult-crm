"""Notification creation service + hooks into key events (E48; Journey J41; issue #230).

The E48 epic is the "in-app notification generation" engine:
:func:`create_notification` is the single primitive that persists an
in-app notification row, and :func:`notify_*` are the thin
per-event helpers called from inside the routers/services that own
those events.

Scope of this issue
-------------------
This slice covers:

* The :class:`app.models.notification.Notification` ORM model and its
  migration (the persisted shape backing the service).
* The creation service (:func:`create_notification` + helpers).
* Hooks for the in-MVP key events:

  * :func:`notify_application_stage_changed` — fires from the E25
    advance-stage endpoint (``POST /applications/{id}/stage``) and
    from the E38/E39/E40 mark-enrolled/rejected/withdrawn endpoints.
    The application's student always gets a notification; the
    assigned counselor gets one if there is one and it is not the
    same person as the student.

* Hooks for the E32 territory events that already exist in the MVP:

  * :func:`notify_document_approved` and :func:`notify_document_rejected`
    fire from the E29 / E30 verifier endpoints. The student who
    uploaded the document is the recipient.

Each hook is intentionally a no-throw wrapper: a notification failure
must not break the originating request (which has already been
validated and partly executed). The originating endpoint still
returns its normal 2xx response; the notification row simply doesn't
appear if the DB is down or the inputs are unusable. Failures are
logged at warning level so the harness and operators can spot them.

Out of scope (tracked as separate issues)
-----------------------------------------
* Email delivery — Epic E49, Journey J42 (issue after #230).
* The notification-center read/mark-read API and UI — Epic E50,
  Journey J43 (sibling issues).
* Meeting-scheduled notifications — Epic E23, Journey J16.
* Owner-invite / new-tenant notifications — covered by E8 / J1
  today (an email is sent; the in-app row is not required for v1).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.notification import Notification
from app.models.student_document import StudentDocument
from app.pipeline.stages import PipelineStage

__all__ = [
    "create_notification",
    "notify_application_stage_changed",
    "notify_document_approved",
    "notify_document_rejected",
]

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_notification(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    title: str,
    message: str,
) -> Optional[Notification]:
    """Persist one :class:`Notification` row and return it.

    Used by every event hook in this module. The caller passes the
    already-resolved ``tenant_id`` and ``user_id`` so the helper does
    not have to re-query (the routers that call it already loaded the
    application / document).

    Errors are swallowed and logged: a notification failure must not
    surface to the user as a 5xx for an otherwise-successful event
    (a flaky notification path should not break stage progression /
    document approval). The function returns ``None`` on failure so
    callers can detect it without raising.

    Args:
        db: Active SQLAlchemy session.
        tenant_id: Tenant scope of the notification.
        user_id: Recipient user id.
        title: Short headline (rendered by the future E50 notification
            center UI).
        message: Free-text body.

    Returns:
        The persisted :class:`Notification`, or ``None`` if persistence
        failed.
    """
    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        message=message,
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    db.add(notification)
    try:
        db.flush()
    except (OperationalError, SQLAlchemyError) as exc:
        logger.warning(
            "notification creation failed (user_id=%s tenant_id=%s): %s",
            user_id,
            tenant_id,
            exc,
        )
        # Roll back ONLY the failed notification insert so the
        # caller's transaction is still usable for the originating
        # event (a flaky notification path must not break stage
        # progression / document approval). We deliberately do NOT
        # re-raise — see the module docstring.
        try:
            db.rollback()
        except SQLAlchemyError:
            pass
        return None
    return notification


def notify_application_stage_changed(
    db: Session,
    *,
    application: Application,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
    actor_user_id: int,
) -> None:
    """Generate in-app notifications for an application stage transition (E25; J18).

    Called from the E25 ``POST /applications/{id}/stage`` endpoint
    (and the E38/E39/E40 mark-enrolled/rejected/withdrawn wrappers,
    which all share the same transition primitive). Generates one
    notification for the student and, when one exists, a separate
    notification for the assigned counselor. Skips the actor (a
    counselor who advances a stage should not also receive a "your
    student's application moved" notification for their own action).

    The student always receives a notification when their application's
    stage changes — including the case where the student is the actor
    (mark-withdrawn / mark-rejected are staff-initiated in practice,
    but the student may also initiate via a future self-service
    flow). Self-actions on one's own application remain useful for
    audit: "Your application moved to X" is meaningful even when the
    student is the actor.

    Args:
        db: Active SQLAlchemy session (shared with the caller — the
            caller commits its own transaction; this helper does not
            commit).
        application: The :class:`Application` that just changed stage.
            Already loaded by the caller; we read ``student_id``,
            ``tenant_id``, and ``assigned_counselor_id`` from it.
        from_stage: The application's prior stage.
        to_stage: The application's new stage.
        actor_user_id: The user who initiated the transition (used
            to suppress a counselor-self-notification).
    """
    title = f"Application moved to {to_stage.value}"
    message = (
        f"Your application changed from '{from_stage.value}' to "
        f"'{to_stage.value}'."
    )

    # The student always gets a notification.
    create_notification(
        db,
        tenant_id=application.tenant_id,
        user_id=application.student_id,
        title=title,
        message=message,
    )

    # The assigned counselor gets a separate notification, but not
    # when they were the actor (avoid notifying a user about their
    # own action).
    counselor_id = application.assigned_counselor_id
    if (
        counselor_id is not None
        and counselor_id != application.student_id
        and counselor_id != actor_user_id
    ):
        counselor_title = f"Assigned application moved to {to_stage.value}"
        counselor_message = (
            f"An application assigned to you moved from "
            f"'{from_stage.value}' to '{to_stage.value}'."
        )
        create_notification(
            db,
            tenant_id=application.tenant_id,
            user_id=counselor_id,
            title=counselor_title,
            message=counselor_message,
        )


def notify_document_approved(
    db: Session,
    *,
    document: StudentDocument,
    application: Application,
    comment: Optional[str],
) -> None:
    """Notify the student that their uploaded document was approved (J22 / J25).

    Called from the E29 ``POST /verifier/documents/{id}/approve``
    endpoint. The student (the original uploader) is the sole
    recipient. The notification text includes the optional
    approval comment so the student sees the verifier's feedback
    in their notification center alongside the standard
    "approved" message.

    Args:
        db: Active SQLAlchemy session.
        document: The :class:`StudentDocument` whose status flipped
            from ``pending`` to ``approved``.
        application: The owning :class:`Application` (loaded by the
            caller). Used here to keep the call site self-documenting
            — the student recipient is the application's student.
        comment: The verifier's optional approval comment (``None``
            or empty string both mean "no comment").
    """
    title = "Document approved"
    body = "Your document was approved."
    if comment:
        body = f"Your document was approved. Comment: {comment}"
    create_notification(
        db,
        tenant_id=application.tenant_id,
        user_id=application.student_id,
        title=title,
        message=body,
    )


def notify_document_rejected(
    db: Session,
    *,
    document: StudentDocument,
    application: Application,
    comment: str,
) -> None:
    """Notify the student that their uploaded document was rejected (J23 / J25).

    Called from the E30 ``POST /verifier/documents/{id}/reject``
    endpoint. The rejection comment is REQUIRED at the E30 layer
    (Journey J23) so it is always present here.

    Args:
        db: Active SQLAlchemy session.
        document: The :class:`StudentDocument` whose status flipped
            from ``pending`` to ``rejected``.
        application: The owning :class:`Application`.
        comment: The verifier's rejection comment (required by E30).
    """
    title = "Document rejected"
    body = f"Your document was rejected. Reason: {comment}"
    create_notification(
        db,
        tenant_id=application.tenant_id,
        user_id=application.student_id,
        title=title,
        message=body,
    )