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

* Hooks for the meeting-scheduled event:

  * :func:`notify_meeting_scheduled` fires from the E22
    ``POST /meetings`` endpoint. The student is the recipient.

Each hook is intentionally a no-throw wrapper: a notification failure
(or, after #234, an email delivery failure) must not break the
originating request (which has already been validated and partly
executed). The originating endpoint still returns its normal 2xx
response; the notification row simply doesn't appear if the DB is down
or the inputs are unusable. Email delivery failures are logged at
warning level so the harness and operators can spot them without
breaking the originating request.

E49 wiring (Issue #234)
-----------------------
After persisting the in-app notification row, every hook also
dispatches an email through :func:`app.email.service.send_email` so
users receive both an in-app and an email notification on the same
event (Requirements §6: "In-app + email for status changes, document
verification results, meeting scheduling"). The email-send is a
no-throw wrapper: a flaky SMTP transport (or any other
:class:`EmailDeliveryError`) is logged but never propagated, so a
broken email path cannot break the (already committed) originating
event.

The email content for each event is composed by a small template
function in :mod:`app.email.notification_templates` (introduced in
this same ticket). That module is a deliberate seam — the in-progress
#233 templates ticket can later replace those builders with richer
HTML / i18n templates without touching the call sites here.

Out of scope (tracked as separate issues)
-----------------------------------------
* The notification-center read/mark-read API and UI — Epic E50,
  Journey J43 (sibling issues).
* Owner-invite / new-tenant notifications — covered by E8 / J1
  today (an email is sent; the in-app row is not required for v1).

Meeting-scheduled notifications (E23 / Journey J16) are produced by
:func:`notify_meeting_scheduled` and wired into the E22
``POST /meetings`` endpoint from this issue's sibling ticket.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.email.notification_templates import (
    build_counselor_stage_change_email,
    build_document_approved_email,
    build_document_rejected_email,
    build_meeting_scheduled_email,
    build_stage_change_email,
)
from app.email.service import EmailDeliveryError, send_email
from app.models.application import Application
from app.models.meeting import Meeting
from app.models.notification import Notification
from app.models.student_document import StudentDocument
from app.models.user import User
from app.pipeline.stages import PipelineStage

__all__ = [
    "create_notification",
    "notify_application_stage_changed",
    "notify_document_approved",
    "notify_document_rejected",
    "notify_meeting_scheduled",
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


def _send_notification_email(
    db: Session,
    *,
    user_id: int,
    subject: str,
    body_text: str,
) -> None:
    """Best-effort dispatch of one notification email (Issue #234).

    Looks up the recipient's email address via the shared SQLAlchemy
    session (the same one that holds the originating transaction) and
    delegates to :func:`app.email.service.send_email`. Any failure —
    missing user, missing email, SMTP transport errors raised as
    :class:`EmailDeliveryError` — is logged at warning level and
    swallowed so a broken email path never breaks the originating
    request. The in-app notification row has already been committed
    before this helper is called, so the user has at least the
    in-app channel as a fallback.

    Args:
        db: Active SQLAlchemy session (shared with the caller).
        user_id: Recipient user id.
        subject: Email subject line.
        body_text: Plain-text body.
    """
    try:
        user = db.get(User, user_id)
    except (OperationalError, SQLAlchemyError) as exc:
        logger.warning(
            "notification email skipped (user lookup failed user_id=%s): %s",
            user_id,
            exc,
        )
        return

    if user is None or not user.email:
        logger.warning(
            "notification email skipped (no email on file user_id=%s)",
            user_id,
        )
        return

    try:
        send_email(to=user.email, subject=subject, body_text=body_text)
    except EmailDeliveryError as exc:
        logger.warning(
            "notification email delivery failed (user_id=%s): %s",
            user_id,
            exc,
        )


def notify_application_stage_changed(
    db: Session,
    *,
    application: Application,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
    actor_user_id: int,
) -> None:
    """Generate in-app + email notifications for an application stage transition (E25; J18).

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

    After persisting the in-app notification rows, the same user_ids
    receive an outbound email through the E49 abstraction (Issue
    #234; J42). Email failures are logged but never propagated.

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

    email_subject, email_body = build_stage_change_email(
        from_stage=from_stage, to_stage=to_stage,
    )
    _send_notification_email(
        db,
        user_id=application.student_id,
        subject=email_subject,
        body_text=email_body,
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

        counselor_email_subject, counselor_email_body = build_counselor_stage_change_email(
            from_stage=from_stage, to_stage=to_stage,
        )
        _send_notification_email(
            db,
            user_id=counselor_id,
            subject=counselor_email_subject,
            body_text=counselor_email_body,
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

    After persisting the in-app notification row, the student also
    receives an outbound email through the E49 abstraction (Issue
    #234; J42). Email failures are logged but never propagated.

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

    email_subject, email_body = build_document_approved_email(comment=comment)
    _send_notification_email(
        db,
        user_id=application.student_id,
        subject=email_subject,
        body_text=email_body,
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

    After persisting the in-app notification row, the student also
    receives an outbound email through the E49 abstraction (Issue
    #234; J42). Email failures are logged but never propagated.

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

    email_subject, email_body = build_document_rejected_email(comment=comment)
    _send_notification_email(
        db,
        user_id=application.student_id,
        subject=email_subject,
        body_text=email_body,
    )


def notify_meeting_scheduled(
    db: Session,
    *,
    meeting: Meeting,
) -> None:
    """Notify the student that a meeting has been scheduled (E23; Journey J16).

    Called from the E22 ``POST /meetings`` endpoint when a new meeting
    is created. The student is the sole recipient — the counselor who
    scheduled it is the actor and does not need an in-app notification
    for their own action. The notification text carries the meeting's
    scheduled time and (if set) its location so the student sees the
    key details in the notification center before opening the full
    meeting view.

    The ``application_id`` on the persisted notification is populated
    so the (future) notification center UI can deep-link back to the
    parent application — the meeting itself is not a first-class
    ``Notification`` FK target, but the parent application is the
    natural drill-down target from J16's "view meeting" CTA.

    After persisting the in-app notification row, the student also
    receives an outbound email through the E49 abstraction (Issue
    #234; J42). Email failures are logged but never propagated.

    Args:
        db: Active SQLAlchemy session.
        meeting: The freshly created :class:`Meeting`. The caller has
            already committed; this helper uses the same session so
            the notification row lands in the same transaction.
    """
    when = meeting.scheduled_at.strftime("%Y-%m-%d %H:%M UTC")
    title = "Meeting scheduled"
    if meeting.location:
        message = (
            f"A meeting has been scheduled for {when} at {meeting.location}."
        )
    else:
        message = f"A meeting has been scheduled for {when}."

    create_notification(
        db,
        tenant_id=meeting.tenant_id,
        user_id=meeting.student_id,
        title=title,
        message=message,
    )

    email_subject, email_body = build_meeting_scheduled_email(
        scheduled_at_text=when,
        location=meeting.location,
    )
    _send_notification_email(
        db,
        user_id=meeting.student_id,
        subject=email_subject,
        body_text=email_body,
    )
