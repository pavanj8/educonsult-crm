"""Unit tests for the E49 wiring notification templates (Issue #234).

``app/email/notification_templates.py`` is the thin module that
composes the ``(subject, body_text)`` pair for each event the E49
wiring ticket dispatches through ``send_email``. These tests pin
the templates' shape so:

* the wiring ticket (#234) knows exactly what it sends per event;
* the in-progress #233 templates ticket has a clear contract to
  enrich without rewriting the call sites (the per-event builders
  return tuples of strings).
"""

from __future__ import annotations

from app.email.notification_templates import (
    build_counselor_stage_change_email,
    build_document_approved_email,
    build_document_rejected_email,
    build_meeting_scheduled_email,
    build_stage_change_email,
)
from app.pipeline.stages import PipelineStage


def test_stage_change_email_includes_from_and_to_stages():
    subject, body = build_stage_change_email(
        from_stage=PipelineStage.COUNSELING,
        to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
    )

    assert "university_shortlisting" in subject
    assert "counseling" in body
    assert "university_shortlisting" in body


def test_counselor_stage_change_email_mentions_assigned_application():
    subject, body = build_counselor_stage_change_email(
        from_stage=PipelineStage.COUNSELING,
        to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
    )

    assert "assigned" in subject.lower()
    assert "assigned to you" in body.lower()


def test_document_approved_email_with_comment_includes_comment():
    subject, body = build_document_approved_email(comment="looks good")
    assert "approved" in subject.lower()
    assert "looks good" in body


def test_document_approved_email_without_comment_omits_comment_marker():
    subject, body = build_document_approved_email(comment=None)
    assert "approved" in subject.lower()
    assert "comment" not in body.lower()


def test_document_rejected_email_includes_reason():
    subject, body = build_document_rejected_email(comment="blurry scan")
    assert "rejected" in subject.lower()
    assert "blurry scan" in body


def test_meeting_scheduled_email_with_location_includes_location():
    subject, body = build_meeting_scheduled_email(
        scheduled_at_text="2026-06-01 14:00 UTC",
        location="Room 4",
    )
    assert "scheduled" in subject.lower()
    assert "Room 4" in body
    assert "2026-06-01 14:00 UTC" in body


def test_meeting_scheduled_email_without_location_skips_at_segment():
    subject, body = build_meeting_scheduled_email(
        scheduled_at_text="2026-06-01 14:00 UTC",
        location=None,
    )
    assert "scheduled" in subject.lower()
    assert " at " not in body
