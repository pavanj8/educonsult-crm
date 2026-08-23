"""Email templates for key CRM events (E49; Journey J42; issue #233).

Plain-text email bodies for the four key notification events that
Requirements §6 / Journey J42 promise the user will receive:

* :func:`send_stage_changed_email` -- application stage change (J18,
  fired from E25 advance-stage and E38/E39/E40 mark-* endpoints).
* :func:`send_document_approved_email` -- document verifier approved
  an upload (J22 / J25).
* :func:`send_document_rejected_email` -- document verifier rejected
  an upload (J23 / J25).
* :func:`send_meeting_scheduled_email` -- counselor scheduled a
  meeting (J15 / J16).

Each template is a small pure function (``build_*_body``) plus a
thin ``send_*_email`` wrapper that calls :func:`app.email.service.send_email`.
Mirrors the existing ``password_reset`` and ``owner_invite`` modules so
the wire-up tickets (#234 / #235) can call them interchangeably.

These templates do NOT touch the database or the in-app
:class:`app.models.notification.Notification` rows -- those are owned
by :mod:`app.services.notifications` (E48). The wire-up in #234 calls
:func:`send_email` for each recipient; the templates here exist so the
wire-up does not need to know the wording, subject lines, or the
shared ``SMTP_FROM`` envelope details.

The body builders are intentionally permissive about missing data
(a missing location / optional counselor name gracefully degrades to
"to be confirmed" rather than raising) so the wire-up can hand them
whatever it has already loaded without a precondition dance.
"""

from __future__ import annotations

from datetime import datetime

from app.email.config import app_base_url
from app.email.service import send_email

__all__ = [
    "build_stage_changed_body",
    "build_document_approved_body",
    "build_document_rejected_body",
    "build_meeting_scheduled_body",
    "send_stage_changed_email",
    "send_document_approved_email",
    "send_document_rejected_email",
    "send_meeting_scheduled_email",
]


def _format_scheduled_at(when: datetime) -> str:
    """Render a meeting time using its timezone's UTC offset.

    Raises:
        ValueError: If ``when`` is naive or otherwise has no valid
            timezone offset.
    """
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("scheduled_at must be a timezone-aware datetime")
    return when.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _student_dashboard_url() -> str:
    """Link target for "view your application" CTAs.

    E50 (notification center) will eventually own deep-links; for v1
    every event email points at the student dashboard which lists all
    applications and meetings. Keeps the templates pluggable for #234
    without a frontend-routes change.
    """
    return f"{app_base_url()}/student"


# --- Stage change ---------------------------------------------------------


def build_stage_changed_body(
    *,
    student_name: str | None,
    from_stage: str,
    to_stage: str,
    university_name: str | None,
    program_name: str | None,
) -> str:
    """Plain-text body for an application stage-change notification.

    Args:
        student_name: Display name for the salutation. ``None`` or
            empty falls back to a neutral greeting.
        from_stage: Previous stage value (already-stringified by the
            caller -- ``PipelineStage.value``).
        to_stage: New stage value.
        university_name: Optional context for which university /
            program the application is for. Helps the student locate
            the right application when they have several in parallel.
        program_name: Optional program context.
    """
    greeting = f"Hi {student_name}," if student_name else "Hi,"

    target_parts = [p for p in (program_name, university_name) if p]
    target = " for " + " / ".join(target_parts) if target_parts else ""

    return (
        f"{greeting}\n\n"
        f"Your application{target} has moved from '{from_stage}' to '{to_stage}'.\n\n"
        f"You can view the full timeline on your dashboard:\n"
        f"  {_student_dashboard_url()}\n\n"
        f"If you have any questions, reply to this email and your "
        f"counselor will be happy to help.\n"
    )


def send_stage_changed_email(
    *,
    to_email: str,
    student_name: str | None,
    from_stage: str,
    to_stage: str,
    university_name: str | None = None,
    program_name: str | None = None,
) -> None:
    """Email a student about an application stage change (J18; E25/E38/E39/E40)."""
    subject = f"Your application moved to {to_stage}"
    body = build_stage_changed_body(
        student_name=student_name,
        from_stage=from_stage,
        to_stage=to_stage,
        university_name=university_name,
        program_name=program_name,
    )
    send_email(to=to_email, subject=subject, body_text=body)


# --- Document review ------------------------------------------------------


def build_document_approved_body(
    *,
    student_name: str | None,
    document_label: str | None,
    comment: str | None,
) -> str:
    """Plain-text body for the document-approved notification (J22 / J25).

    An empty-string ``comment`` is treated as no comment, so no
    Verifier's note line is emitted.
    """
    greeting = f"Hi {student_name}," if student_name else "Hi,"

    label = document_label or "your document"
    if comment:
        comment_block = (
            f"\nVerifier's note: {comment}\n"
        )
    else:
        comment_block = ""

    return (
        f"{greeting}\n\n"
        f"Good news -- {label} has been approved.\n"
        f"{comment_block}\n"
        f"You can view the checklist on your dashboard:\n"
        f"  {_student_dashboard_url()}\n"
    )


def send_document_approved_email(
    *,
    to_email: str,
    student_name: str | None,
    document_label: str | None,
    comment: str | None,
) -> None:
    """Email the student that their document was approved (J22 / J25)."""
    subject = "Your document was approved"
    body = build_document_approved_body(
        student_name=student_name,
        document_label=document_label,
        comment=comment,
    )
    send_email(to=to_email, subject=subject, body_text=body)


def build_document_rejected_body(
    *,
    student_name: str | None,
    document_label: str | None,
    comment: str,
) -> str:
    """Plain-text body for the document-rejected notification (J23 / J25).

    ``comment`` is required by the E30 endpoint (Journey J23) so the
    template always has something to put in the reason slot. A guard
    keeps the function tolerant of an empty string for defensive
    coding.
    """
    greeting = f"Hi {student_name}," if student_name else "Hi,"

    label = document_label or "your document"
    reason = comment.strip() or "No reason provided."

    return (
        f"{greeting}\n\n"
        f"Unfortunately, {label} was rejected and needs to be re-uploaded.\n\n"
        f"Reason: {reason}\n\n"
        f"You can re-upload the corrected document from your dashboard:\n"
        f"  {_student_dashboard_url()}\n"
    )


def send_document_rejected_email(
    *,
    to_email: str,
    student_name: str | None,
    document_label: str | None,
    comment: str,
) -> None:
    """Email the student that their document was rejected (J23 / J25)."""
    subject = "Your document was rejected"
    body = build_document_rejected_body(
        student_name=student_name,
        document_label=document_label,
        comment=comment,
    )
    send_email(to=to_email, subject=subject, body_text=body)


# --- Meeting scheduled ----------------------------------------------------


def build_meeting_scheduled_body(
    *,
    student_name: str | None,
    scheduled_at: datetime,
    duration_minutes: int,
    location: str | None,
    counselor_name: str | None,
) -> str:
    """Plain-text body for the meeting-scheduled notification (J16; E23)."""
    greeting = f"Hi {student_name}," if student_name else "Hi,"

    when = _format_scheduled_at(scheduled_at)
    where = location or "to be confirmed"
    with_who = f" with {counselor_name}" if counselor_name else ""

    return (
        f"{greeting}\n\n"
        f"A meeting{with_who} has been scheduled for {when} "
        f"({duration_minutes} minutes).\n"
        f"Location: {where}\n\n"
        f"You can see this and upcoming meetings on your dashboard:\n"
        f"  {_student_dashboard_url()}\n"
    )


def send_meeting_scheduled_email(
    *,
    to_email: str,
    student_name: str | None,
    scheduled_at: datetime,
    duration_minutes: int,
    location: str | None,
    counselor_name: str | None,
) -> None:
    """Email the student that a meeting has been scheduled (J16; E22/E23)."""
    subject = "A meeting has been scheduled"
    body = build_meeting_scheduled_body(
        student_name=student_name,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        location=location,
        counselor_name=counselor_name,
    )
    send_email(to=to_email, subject=subject, body_text=body)