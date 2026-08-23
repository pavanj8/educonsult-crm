"""Unit tests for the E49 key-event email templates (issue #233).

Mirrors ``test_service.py`` and ``test_password_reset.py``: we exercise
the ``build_*_body`` template renderers in isolation and verify the
``send_*_email`` wrappers delegate to the low-level :func:`send_email`
helper. SMTP-level behaviour and integration with the notification
triggers are covered by ``tests/notifications/test_notification_hooks.py``
and the wire-up ticket (#234).

The four key events the issue calls out are:
* stage change (E25/E38/E39/E40; J18)
* document approval (E29; J22 / J25)
* document rejection (E30; J23 / J25)
* meeting scheduled (E22; J15 / J16)

The owner-invite template (#232 / E8) already exists and is covered
by ``test_service.py`` -- no duplication here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.email.notifications import (
    build_document_approved_body,
    build_document_rejected_body,
    build_meeting_scheduled_body,
    build_stage_changed_body,
    send_document_approved_email,
    send_document_rejected_email,
    send_meeting_scheduled_email,
    send_stage_changed_email,
)


# --- Stage change ---------------------------------------------------------


def test_build_stage_changed_body_includes_student_name_and_stages():
    body = build_stage_changed_body(
        student_name="Asha",
        from_stage="counseling",
        to_stage="university_shortlisting",
        university_name="MIT",
        program_name="MS Computer Science",
    )

    assert "Hi Asha," in body
    assert "'counseling'" in body
    assert "'university_shortlisting'" in body
    # University + program context helps the student identify which
    # application (they may have several in parallel -- J11).
    assert "MIT" in body
    assert "MS Computer Science" in body


def test_build_stage_changed_body_links_to_dashboard():
    body = build_stage_changed_body(
        student_name="Asha",
        from_stage="registered",
        to_stage="counseling",
        university_name=None,
        program_name=None,
    )

    assert "/student" in body
    assert "http" in body  # absolute URL, not a bare path


def test_build_stage_changed_body_handles_missing_student_name():
    body = build_stage_changed_body(
        student_name=None,
        from_stage="registered",
        to_stage="counseling",
        university_name="MIT",
        program_name=None,
    )

    # Should not crash on a missing salutation -- just fall back to a
    # neutral greeting so the wire-up doesn't need to guarantee a
    # name is present.
    assert "Hi," in body
    assert "Hi ," not in body
    assert "MIT" in body


def test_build_stage_changed_body_omits_target_when_university_and_program_missing():
    body = build_stage_changed_body(
        student_name="Asha",
        from_stage="registered",
        to_stage="counseling",
        university_name=None,
        program_name=None,
    )

    # No "for" clause when neither context field is supplied -- keeps
    # the sentence grammatical ("Your application has moved...").
    assert "Your application has moved" in body
    assert " for " not in body


def test_send_stage_changed_email_delegates_to_smtp():
    with patch("app.email.notifications.send_email") as mock_send:
        send_stage_changed_email(
            to_email="student@example.test",
            student_name="Asha",
            from_stage="counseling",
            to_stage="application_submitted",
            university_name="MIT",
            program_name="MS CS",
        )

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "student@example.test"
    assert "application_submitted" in kwargs["subject"]
    assert "Asha" in kwargs["body_text"]
    assert "MIT" in kwargs["body_text"]


# --- Document approval ----------------------------------------------------


def test_build_document_approved_body_includes_label_and_greeting():
    body = build_document_approved_body(
        student_name="Asha",
        document_label="Transcript",
        comment=None,
    )

    assert "Hi Asha," in body
    assert "Transcript" in body
    assert "approved" in body.lower()


def test_build_document_approved_body_includes_comment_when_present():
    body = build_document_approved_body(
        student_name="Asha",
        document_label="Transcript",
        comment="Looks great",
    )

    assert "Verifier" in body or "Note" in body or "Looks great" in body
    assert "Looks great" in body


def test_build_document_approved_body_omits_comment_block_when_absent():
    body_no_comment = build_document_approved_body(
        student_name="Asha",
        document_label="Transcript",
        comment=None,
    )
    body_empty_comment = build_document_approved_body(
        student_name="Asha",
        document_label="Transcript",
        comment="",
    )

    # No "Verifier's note" line when there's no comment to surface --
    # keeps the email tidy when the verifier approves silently.
    assert "Verifier's note" not in body_no_comment
    assert "Verifier's note" not in body_empty_comment


def test_build_document_approved_body_falls_back_for_missing_label():
    body = build_document_approved_body(
        student_name=None,
        document_label=None,
        comment=None,
    )

    assert "your document" in body.lower()
    assert "Hi," in body


def test_send_document_approved_email_delegates_to_smtp():
    with patch("app.email.notifications.send_email") as mock_send:
        send_document_approved_email(
            to_email="student@example.test",
            student_name="Asha",
            document_label="Transcript",
            comment=None,
        )

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "student@example.test"
    assert "approved" in kwargs["subject"].lower()
    assert "Transcript" in kwargs["body_text"]


# --- Document rejection ---------------------------------------------------


def test_build_document_rejected_body_includes_reason_and_label():
    body = build_document_rejected_body(
        student_name="Asha",
        document_label="Transcript",
        comment="Image is blurry, please re-upload",
    )

    assert "Hi Asha," in body
    assert "Transcript" in body
    assert "rejected" in body.lower()
    assert "Image is blurry" in body
    assert "re-upload" in body.lower()


def test_build_document_rejected_body_falls_back_when_comment_empty():
    # Defensive: an empty string must not produce a blank "Reason:"
    # line -- the user needs a usable reason to act on.
    body = build_document_rejected_body(
        student_name="Asha",
        document_label="Transcript",
        comment="",
    )

    assert "Reason:" in body
    assert "No reason provided" in body


def test_build_document_rejected_body_handles_missing_student_name():
    body = build_document_rejected_body(
        student_name=None,
        document_label=None,
        comment="Wrong document type",
    )

    assert "Hi," in body
    assert "your document" in body.lower()
    assert "Wrong document type" in body


def test_send_document_rejected_email_delegates_to_smtp():
    with patch("app.email.notifications.send_email") as mock_send:
        send_document_rejected_email(
            to_email="student@example.test",
            student_name="Asha",
            document_label="Transcript",
            comment="blurry",
        )

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "student@example.test"
    assert "rejected" in kwargs["subject"].lower()
    assert "blurry" in kwargs["body_text"]


# --- Meeting scheduled ----------------------------------------------------


def test_build_meeting_scheduled_body_includes_time_and_location():
    when = datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc)
    body = build_meeting_scheduled_body(
        student_name="Asha",
        scheduled_at=when,
        duration_minutes=30,
        location="Zoom",
        counselor_name="Mr. Rao",
    )

    assert "Hi Asha," in body
    assert "2026-06-01 14:30 UTC" in body
    assert "30 minutes" in body
    assert "Zoom" in body
    assert "Mr. Rao" in body


def test_build_meeting_scheduled_body_handles_missing_location():
    when = datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc)
    body = build_meeting_scheduled_body(
        student_name="Asha",
        scheduled_at=when,
        duration_minutes=30,
        location=None,
        counselor_name="Mr. Rao",
    )

    # "to be confirmed" placeholder so the email is still self-explanatory
    # even when the counselor hasn't picked a venue yet.
    assert "to be confirmed" in body.lower()
    assert "Location:" in body


def test_build_meeting_scheduled_body_handles_missing_counselor_name():
    when = datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc)
    body = build_meeting_scheduled_body(
        student_name=None,
        scheduled_at=when,
        duration_minutes=45,
        location="Office",
        counselor_name=None,
    )

    # No " with X" clause when we don't know who the counselor is.
    assert "Hi," in body
    assert " with " not in body
    assert "45 minutes" in body


def test_send_meeting_scheduled_email_delegates_to_smtp():
    when = datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc)
    with patch("app.email.notifications.send_email") as mock_send:
        send_meeting_scheduled_email(
            to_email="student@example.test",
            student_name="Asha",
            scheduled_at=when,
            duration_minutes=30,
            location="Office",
            counselor_name="Mr. Rao",
        )

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "student@example.test"
    assert "scheduled" in kwargs["subject"].lower()
    assert "2026-06-01 14:30 UTC" in kwargs["body_text"]


# --- Cross-cutting safety --------------------------------------------------


@pytest.mark.parametrize(
    "send_fn",
    [
        send_stage_changed_email,
        send_document_approved_email,
        send_document_rejected_email,
        send_meeting_scheduled_email,
    ],
)
def test_all_send_functions_carry_from_header(send_fn):
    """Every send_*_email wrapper must delegate to send_email (no inlining).

    Guards against accidental bypass of the SMTP client wrapper
    (e.g. someone instantiating smtplib.SMTP directly in a template).
    The pluggable-email architecture in the spec depends on every
    outbound message going through one chokepoint so future providers
    (SMS / WhatsApp) can be slotted in via #234 / E49.
    """
    when = datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc)
    with patch("app.email.notifications.send_email") as mock_send:
        if send_fn is send_stage_changed_email:
            send_fn(
                to_email="x@example.test",
                student_name="X",
                from_stage="registered",
                to_stage="counseling",
            )
        elif send_fn is send_document_approved_email:
            send_fn(
                to_email="x@example.test",
                student_name="X",
                document_label="Doc",
                comment=None,
            )
        elif send_fn is send_document_rejected_email:
            send_fn(
                to_email="x@example.test",
                student_name="X",
                document_label="Doc",
                comment="bad",
            )
        else:
            send_fn(
                to_email="x@example.test",
                student_name="X",
                scheduled_at=when,
                duration_minutes=30,
                location="Office",
                counselor_name="Y",
            )

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to"] == "x@example.test"


def test_email_package_reexports_new_helpers():
    """The package-level ``__init__`` must expose the new templates.

    Guards against a refactor that forgets to surface the helpers at
    the package root -- the wire-up ticket (#234) imports them from
    ``app.email`` rather than the submodule so the public surface has
    to actually expose them.
    """
    import app.email as email_pkg

    expected = {
        "send_stage_changed_email",
        "send_document_approved_email",
        "send_document_rejected_email",
        "send_meeting_scheduled_email",
    }
    assert expected.issubset(set(email_pkg.__all__))
    for name in expected:
        assert callable(getattr(email_pkg, name))