"""Plain-text email templates for the E49 wiring ticket (Issue #234).

This module is the seam the existing E48 notification triggers
(:mod:`app.services.notifications`) call into to compose the
``(subject, body)`` pair for every outbound notification email.
:func:`app.email.service.send_email` is then called by the trigger,
not by this module — this module is template-only.

Why templates live in their own module
--------------------------------------
The four events the E49 wiring ticket cares about (stage change,
document review, meeting scheduled) are all generated from
``app/services/notifications.py``. Keeping the email composition
separate from the trigger keeps the in-app notification code free of
template strings and gives the (in-progress) #233 templates ticket a
clean place to land richer HTML / i18n templates later without
rewriting the call sites.

The templates here intentionally match the in-app notification text
so the user sees the same wording in their inbox as in the
notification center — see E48 / J41.

Out of scope (tracked as separate issues)
-----------------------------------------
* Richer per-event templates (HTML, branding, i18n) — issue #233.
* SMS / WhatsApp providers behind the same call sites — out of v1
  scope (Requirements §6: "architecture kept pluggable for SMS /
  WhatsApp later").
"""

from app.pipeline.stages import PipelineStage

__all__ = [
    "build_stage_change_email",
    "build_counselor_stage_change_email",
    "build_document_approved_email",
    "build_document_rejected_email",
    "build_meeting_scheduled_email",
]


def build_stage_change_email(
    *,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
) -> tuple[str, str]:
    """Return ``(subject, body_text)`` for an application stage change email."""
    subject = f"Your application moved to {to_stage.value}"
    body = (
        f"Hello,\n\n"
        f"Your application changed from '{from_stage.value}' to "
        f"'{to_stage.value}'.\n\n"
        f"Sign in to view the details.\n"
    )
    return subject, body


def build_counselor_stage_change_email(
    *,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
) -> tuple[str, str]:
    """Return ``(subject, body_text)`` for the counselor's stage-change copy.

    The counselor's copy differs from the student's so the recipient
    can tell at a glance that the message is about an *assigned*
    application rather than one of their own — the in-app copy in
    :func:`app.services.notifications.notify_application_stage_changed`
    uses the same distinction.
    """
    subject = f"Assigned application moved to {to_stage.value}"
    body = (
        f"Hello,\n\n"
        f"An application assigned to you moved from "
        f"'{from_stage.value}' to '{to_stage.value}'.\n\n"
        f"Sign in to view the details.\n"
    )
    return subject, body


def build_document_approved_email(*, comment: str | None) -> tuple[str, str]:
    """Return ``(subject, body_text)`` for a document-approved email (J22)."""
    subject = "Your document was approved"
    if comment:
        body = (
            f"Hello,\n\n"
            f"Your document was approved. Comment: {comment}\n\n"
            f"Sign in to view the details.\n"
        )
    else:
        body = (
            "Hello,\n\n"
            "Your document was approved.\n\n"
            "Sign in to view the details.\n"
        )
    return subject, body


def build_document_rejected_email(*, comment: str) -> tuple[str, str]:
    """Return ``(subject, body_text)`` for a document-rejected email (J23).

    The ``comment`` (rejection reason) is required at the E30 router
    layer (Journey J23) and is therefore always present here.
    """
    subject = "Your document was rejected"
    body = (
        f"Hello,\n\n"
        f"Your document was rejected. Reason: {comment}\n\n"
        f"Please re-upload a corrected document.\n"
    )
    return subject, body


def build_meeting_scheduled_email(
    *,
    scheduled_at_text: str,
    location: str | None,
) -> tuple[str, str]:
    """Return ``(subject, body_text)`` for a meeting-scheduled email (J16)."""
    subject = "A meeting has been scheduled"
    if location:
        body = (
            f"Hello,\n\n"
            f"A meeting has been scheduled for {scheduled_at_text} "
            f"at {location}.\n\n"
            f"Sign in to view the details.\n"
        )
    else:
        body = (
            f"Hello,\n\n"
            f"A meeting has been scheduled for {scheduled_at_text}.\n\n"
            f"Sign in to view the details.\n"
        )
    return subject, body
