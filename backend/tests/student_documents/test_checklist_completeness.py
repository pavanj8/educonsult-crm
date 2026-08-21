"""Tests for the E27 checklist completeness calculation (issue #178).

The completeness helper (:func:`compute_checklist_completeness`) is the
``checklist completeness calculation`` half of E27 ("Tests: upload
validation and checklist completeness calculation"). It takes the
merged E26 checklist view (a list of items, each with a ``required``
flag and an optional ``upload`` whose ``status`` is the
:class:`StudentDocumentStatus` value) and returns a
:class:`ChecklistCompletenessSummary` describing how far the student
is from being "done" with their documents.

The test file is organized in three sections, matching the helper's
design contract:

* **Pure-function tests** — exercise the helper directly with simple
  data classes, no DB. This is the fast, deterministic unit-test
  surface and where the contract is fully pinned.
* **End-to-end through the E26 endpoint** — seed real
  ``ChecklistItemTemplate`` + ``StudentDocument`` rows, hit
  ``GET /applications/{id}/checklist``, and assert the summary matches
  what we'd derive from the response. This pins the integration with
  the live ORM shapes.
* **Public-API contract** — assert that
  :func:`compute_checklist_completeness` and
  :class:`ChecklistCompletenessSummary` are exported from
  :mod:`app.storage` (the way the rest of the codebase reaches them).

The upload-validation half of issue #178 is already covered by the
``tests/student_documents/test_upload_validation.py`` file (sibling
ticket #176). This file complements — does not duplicate — that
coverage.

Traceability
------------

* Requirements §5 (per-stage/program checklist templates; ``required``
  flag drives whether an item blocks document verification).
* Journey J20 (Student uploads a document against a checklist item).
* Epic E27 (Student Document Upload); this is the completeness-
  calculation test suite (issue #178). Sibling tickets own the
  StudentDocument model (#174), the upload endpoint (#175), the
  validation layer (#176), the upload UI (#177), and the merged
  checklist read endpoint (#173 / E26).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.models.student_document import StudentDocumentStatus
from app.models.tenant import Tenant
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.storage import (
    ChecklistCompletenessItem,
    ChecklistCompletenessSummary,
    compute_checklist_completeness,
)
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.checklist.helpers import seed_checklist_template, seed_student_document
from tests.factories.users import make_authenticated_user, make_db_user
from tests.master_data.helpers import seed_master_data_chain


# ---------------------------------------------------------------------------
# Test doubles for the pure-function tests
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StubUpload:
    """Minimal upload stand-in that satisfies the helper's Protocol."""

    status: str


@dataclass(frozen=True)
class _StubItem:
    """Minimal item stand-in that satisfies the helper's Protocol.

    Lets the unit tests construct arbitrary shapes without an ORM
    session, a Pydantic schema, or a real checklist view — exactly
    the property the helper's Protocol-based design is meant to give
    callers.
    """

    required: bool
    upload: _StubUpload | None = None


def _required(upload_status: str | None) -> _StubItem:
    return _StubItem(required=True, upload=_StubUpload(upload_status) if upload_status is not None else None)


def _optional(upload_status: str | None) -> _StubItem:
    return _StubItem(required=False, upload=_StubUpload(upload_status) if upload_status is not None else None)


# ---------------------------------------------------------------------------
# Pure-function tests: empty checklist
# ---------------------------------------------------------------------------


def test_compute_checklist_completeness_empty_items():
    """An empty checklist is trivially complete (zero required items)."""
    summary = compute_checklist_completeness([])

    assert summary == ChecklistCompletenessSummary(
        total_items=0,
        required_items=0,
        optional_items=0,
        approved_count=0,
        pending_count=0,
        rejected_count=0,
        missing_count=0,
        is_complete=True,
    )


def test_compute_checklist_completeness_empty_items_is_vacuously_complete():
    """Vacuously-True ``is_complete`` for an empty checklist is the
    documented behaviour (no required items → nothing to do)."""
    summary = compute_checklist_completeness([])
    assert summary.is_complete is True


def test_compute_checklist_completeness_handles_single_pass_iterator():
    """The helper iterates the input exactly once and works with any
    iterable — generators included (the docstring promises this)."""
    def _gen():
        yield _required("approved")
        yield _required("pending")

    summary = compute_checklist_completeness(_gen())
    assert summary.total_items == 2
    assert summary.required_items == 2
    assert summary.approved_count == 1
    assert summary.pending_count == 1


def test_compute_checklist_completeness_accepts_plain_dict_items():
    """The helper accepts plain ``dict`` items (with ``required`` and
    ``upload`` keys) — this lets callers feed the JSON body of the live
    E26 endpoint directly without a reconstruction step."""
    items = [
        {"required": True, "upload": {"status": "approved"}},
        {"required": True, "upload": None},
        {"required": False, "upload": {"status": "rejected"}},
    ]
    summary = compute_checklist_completeness(items)

    assert summary.total_items == 3
    assert summary.required_items == 2
    assert summary.optional_items == 1
    assert summary.approved_count == 1
    assert summary.missing_count == 1
    assert summary.is_complete is False


def test_compute_checklist_completeness_accepts_dict_with_missing_required_key():
    """A dict item without a ``required`` key is treated as optional
    (mirrors the Pydantic ``required: bool`` default via ``.get``)."""
    items = [
        {"upload": {"status": "approved"}},  # no "required" key
    ]
    summary = compute_checklist_completeness(items)
    assert summary.required_items == 0
    assert summary.optional_items == 1
    assert summary.is_complete is True


def test_compute_checklist_completeness_accepts_dict_with_null_status():
    """A dict upload whose ``status`` is ``None`` (the JSON encoding of
    a missing upload in some pre-serialisation paths) is treated as
    "no upload"."""
    items = [
        {"required": True, "upload": {"status": None}},
    ]
    summary = compute_checklist_completeness(items)
    assert summary.missing_count == 1
    assert summary.is_complete is False


# ---------------------------------------------------------------------------
# Pure-function tests: required-only checklists
# ---------------------------------------------------------------------------


def test_compute_checklist_completeness_all_required_approved():
    """All required items approved → is_complete is True; every counter zero except approved."""
    items = [
        _required("approved"),
        _required("approved"),
        _required("approved"),
    ]
    summary = compute_checklist_completeness(items)

    assert summary.total_items == 3
    assert summary.required_items == 3
    assert summary.optional_items == 0
    assert summary.approved_count == 3
    assert summary.pending_count == 0
    assert summary.rejected_count == 0
    assert summary.missing_count == 0
    assert summary.is_complete is True


def test_compute_checklist_completeness_all_required_missing():
    """All required items missing → is_complete is False; missing_count == required_items."""
    items = [
        _required(None),
        _required(None),
    ]
    summary = compute_checklist_completeness(items)

    assert summary.total_items == 2
    assert summary.required_items == 2
    assert summary.optional_items == 0
    assert summary.approved_count == 0
    assert summary.pending_count == 0
    assert summary.rejected_count == 0
    assert summary.missing_count == 2
    assert summary.is_complete is False


def test_compute_checklist_completeness_all_required_pending():
    """All required items pending → is_complete is False; pending_count == required_items."""
    items = [
        _required("pending"),
        _required("pending"),
        _required("pending"),
        _required("pending"),
    ]
    summary = compute_checklist_completeness(items)

    assert summary.total_items == 4
    assert summary.required_items == 4
    assert summary.optional_items == 0
    assert summary.approved_count == 0
    assert summary.pending_count == 4
    assert summary.rejected_count == 0
    assert summary.missing_count == 0
    assert summary.is_complete is False


def test_compute_checklist_completeness_all_required_rejected():
    """All required items rejected → is_complete is False; rejected_count == required_items.

    The E31 re-upload flow exists for this exact state; completeness
    must NOT count a rejected upload as "done" (only APPROVED does).
    """
    items = [
        _required("rejected"),
        _required("rejected"),
    ]
    summary = compute_checklist_completeness(items)

    assert summary.total_items == 2
    assert summary.required_items == 2
    assert summary.optional_items == 0
    assert summary.approved_count == 0
    assert summary.pending_count == 0
    assert summary.rejected_count == 2
    assert summary.missing_count == 0
    assert summary.is_complete is False


def test_compute_checklist_completeness_mixed_required_states():
    """Required items spread across all four states are counted independently."""
    items = [
        _required("approved"),  # done
        _required("approved"),  # done
        _required("pending"),   # under review
        _required("rejected"),  # needs re-upload
        _required(None),        # never uploaded
    ]
    summary = compute_checklist_completeness(items)

    assert summary.total_items == 5
    assert summary.required_items == 5
    assert summary.optional_items == 0
    assert summary.approved_count == 2
    assert summary.pending_count == 1
    assert summary.rejected_count == 1
    assert summary.missing_count == 1
    assert summary.is_complete is False


def test_compute_checklist_completeness_partial_approval_is_not_complete():
    """A checklist with at least one non-approved required item is not complete."""
    items = [
        _required("approved"),
        _required("approved"),
        _required("pending"),  # one item still in review
    ]
    summary = compute_checklist_completeness(items)

    assert summary.approved_count == 2
    assert summary.required_items == 3
    assert summary.is_complete is False


# ---------------------------------------------------------------------------
# Pure-function tests: optional items do not affect completeness
# ---------------------------------------------------------------------------


def test_compute_checklist_completeness_optional_items_do_not_block_completion():
    """An optional item missing its upload does NOT block completeness."""
    items = [
        _required("approved"),
        _optional(None),  # optional, never uploaded
    ]
    summary = compute_checklist_completeness(items)

    assert summary.total_items == 2
    assert summary.required_items == 1
    assert summary.optional_items == 1
    assert summary.approved_count == 1
    assert summary.missing_count == 0  # optional missing → no missing count
    assert summary.is_complete is True


def test_compute_checklist_completeness_optional_items_never_contribute_to_counts():
    """Required-only counters ignore optional items regardless of upload state."""
    items = [
        _required("approved"),
        _required("pending"),
        _optional("approved"),
        _optional("pending"),
        _optional("rejected"),
        _optional(None),
    ]
    summary = compute_checklist_completeness(items)

    # Total / required / optional partition the input.
    assert summary.total_items == 6
    assert summary.required_items == 2
    assert summary.optional_items == 4
    # Required-only counters: approved=1, pending=1, rejected=0, missing=0.
    assert summary.approved_count == 1
    assert summary.pending_count == 1
    assert summary.rejected_count == 0
    assert summary.missing_count == 0
    assert summary.is_complete is False


def test_compute_checklist_completeness_only_optional_items_is_vacuously_complete():
    """A checklist with zero required items is vacuously complete, even when
    optional items are missing or rejected. This is the only way the
    helper can return ``is_complete=True`` without an approval."""
    items = [
        _optional(None),
        _optional("rejected"),
        _optional("pending"),
    ]
    summary = compute_checklist_completeness(items)

    assert summary.required_items == 0
    assert summary.optional_items == 3
    assert summary.approved_count == 0
    assert summary.missing_count == 0
    assert summary.rejected_count == 0
    assert summary.pending_count == 0
    assert summary.is_complete is True


# ---------------------------------------------------------------------------
# Pure-function tests: forward-compat / robustness
# ---------------------------------------------------------------------------


def test_compute_checklist_completeness_unknown_status_is_treated_as_not_done():
    """An unknown upload status (forward-compat enum value) is treated
    as "not done" — the helper does not raise and does not falsely
    count it as approved. This pins the contract from the docstring."""
    items = [
        _required("approved"),
        _required("flagged_for_review"),  # hypothetical future enum value
    ]
    summary = compute_checklist_completeness(items)

    assert summary.required_items == 2
    assert summary.approved_count == 1  # only the explicit approved
    assert summary.is_complete is False


def test_compute_checklist_completeness_with_real_schema_items():
    """The helper works with the real Pydantic schemas (Pydantic models
    satisfy the structural Protocol via attribute access)."""
    from app.schemas.checklist import ChecklistItemView, ChecklistUploadSummary

    approved_at = datetime.now(timezone.utc)
    items = [
        ChecklistItemView(
            template_id=1,
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Passport copy",
            description=None,
            required=True,
            order_index=1,
            upload=ChecklistUploadSummary(
                id=1,
                status=StudentDocumentStatus.APPROVED,
                original_filename="passport.pdf",
                uploaded_at=approved_at,
                verified_at=approved_at,
                rejection_reason=None,
            ),
        ),
        ChecklistItemView(
            template_id=2,
            stage=PipelineStage.DOCUMENT_VERIFICATION,
            name="Transcript",
            description=None,
            required=True,
            order_index=2,
            upload=None,
        ),
    ]

    summary = compute_checklist_completeness(items)

    assert summary.total_items == 2
    assert summary.required_items == 2
    assert summary.approved_count == 1
    assert summary.missing_count == 1
    assert summary.is_complete is False


# ---------------------------------------------------------------------------
# Pure-function tests: dataclass equality / immutability
# ---------------------------------------------------------------------------


def test_checklist_completeness_summary_is_frozen_dataclass():
    """The summary is a frozen dataclass — callers cannot accidentally
    mutate a count (which would silently desync from the items list)."""
    summary = compute_checklist_completeness([_required("approved")])
    with pytest.raises((AttributeError, Exception)):  # FrozenInstanceError or AttributeError
        summary.approved_count = 999  # type: ignore[misc]


def test_checklist_completeness_summary_equality():
    """Two summaries derived from equivalent inputs are equal (dataclass
    equality is value-based)."""
    a = compute_checklist_completeness([_required("approved"), _required(None)])
    b = compute_checklist_completeness([_required("approved"), _required(None)])
    assert a == b


# ---------------------------------------------------------------------------
# Public-API surface (export contract)
# ---------------------------------------------------------------------------


def test_compute_checklist_completeness_is_exported_from_app_storage():
    """The helper is reachable via ``app.storage.compute_checklist_completeness``
    (the public surface used by tests and future callers)."""
    from app.storage import compute_checklist_completeness as exported

    assert exported is compute_checklist_completeness


def test_checklist_completeness_summary_is_exported_from_app_storage():
    """The summary dataclass is reachable via ``app.storage.ChecklistCompletenessSummary``."""
    from app.storage import ChecklistCompletenessSummary as exported

    assert exported is ChecklistCompletenessSummary


def test_checklist_completeness_item_protocol_is_exported_from_app_storage():
    """The structural Protocol is exported for downstream test mocks / type hints."""
    from app.storage import ChecklistCompletenessItem as exported

    assert exported is ChecklistCompletenessItem


# ---------------------------------------------------------------------------
# End-to-end: helper agrees with the live E26 endpoint
# ---------------------------------------------------------------------------


def _create_tenant(db_session, *, name: str = "Apex EduConsult", slug: str = "apex") -> Tenant:
    tenant = Tenant(name=name, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _auth_as_student(override_authenticated_user, *, user_id, tenant_id, branch_id):
    override_authenticated_user(
        make_authenticated_user(
            Role.STUDENT,
            user_id=user_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
    )


def test_checklist_completeness_matches_endpoint_with_no_templates(
    client, db_session, override_authenticated_user
):
    """No templates → endpoint items=[] → completeness is empty + vacuously complete."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="completeness-empty@example.test",
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        university_id=chain[1].id,
        program_id=chain[2].id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )
    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    body = response.json()

    summary = compute_checklist_completeness(body["items"])
    assert summary.total_items == 0
    assert summary.required_items == 0
    assert summary.is_complete is True


def test_checklist_completeness_matches_endpoint_with_mixed_required_states(
    client, db_session, override_authenticated_user
):
    """The helper's summary agrees with what the E26 endpoint returns for
    a realistic mixed-state checklist (one of each: approved, pending,
    rejected, missing)."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="completeness-mixed@example.test",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="completeness-verifier@example.test",
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        university_id=chain[1].id,
        program_id=chain[2].id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )

    # 5 required templates in 4 distinct states.
    approved_template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
        order_index=1,
    )
    pending_template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="10th transcripts",
        order_index=2,
    )
    rejected_template = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="LOR 1",
        order_index=3,
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Statement of purpose",
        order_index=4,
    )
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Optional: photo",
        required=False,
        order_index=5,
    )

    now = datetime.now(timezone.utc)
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=approved_template.id,
        status=StudentDocumentStatus.APPROVED,
        uploaded_by_user_id=student.id,
        verified_by_user_id=verifier.id,
        verified_at=now - timedelta(hours=1),
    )
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=pending_template.id,
        status=StudentDocumentStatus.PENDING,
        uploaded_by_user_id=student.id,
        uploaded_at=now - timedelta(minutes=10),
    )
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=rejected_template.id,
        status=StudentDocumentStatus.REJECTED,
        uploaded_by_user_id=student.id,
        verified_by_user_id=verifier.id,
        verified_at=now - timedelta(hours=2),
        rejection_reason="Image too blurry",
    )
    # missing_template deliberately has no StudentDocument row.

    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 5

    summary = compute_checklist_completeness(body["items"])

    assert summary.total_items == 5
    assert summary.required_items == 4
    assert summary.optional_items == 1
    assert summary.approved_count == 1
    assert summary.pending_count == 1
    assert summary.rejected_count == 1
    assert summary.missing_count == 1
    assert summary.is_complete is False


def test_checklist_completeness_is_complete_when_all_required_approved(
    client, db_session, override_authenticated_user
):
    """End-to-end "all required approved" scenario: the helper agrees
    the student is done, even though optional items may still be missing."""
    tenant = _create_tenant(db_session)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    chain = seed_master_data_chain(db_session, tenant_id=tenant.id)
    student = make_db_user(
        db_session,
        Role.STUDENT,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="completeness-done@example.test",
    )
    verifier = make_db_user(
        db_session,
        Role.DOCUMENT_VERIFIER,
        tenant_id=tenant.id,
        branch_id=branch.id,
        email="completeness-done-verifier@example.test",
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        student_id=student.id,
        university_id=chain[1].id,
        program_id=chain[2].id,
        stage=PipelineStage.DOCUMENT_VERIFICATION,
    )

    req1 = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Passport copy",
        order_index=1,
    )
    req2 = seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Transcript",
        order_index=2,
    )
    # One optional item, never uploaded.
    seed_checklist_template(
        db_session,
        tenant_id=tenant.id,
        stage=application.stage,
        program_id=None,
        name="Optional: photo",
        required=False,
        order_index=3,
    )

    now = datetime.now(timezone.utc)
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=req1.id,
        status=StudentDocumentStatus.APPROVED,
        uploaded_by_user_id=student.id,
        verified_by_user_id=verifier.id,
        verified_at=now - timedelta(hours=1),
    )
    seed_student_document(
        db_session,
        tenant_id=tenant.id,
        application_id=application.id,
        checklist_item_template_id=req2.id,
        status=StudentDocumentStatus.APPROVED,
        uploaded_by_user_id=student.id,
        verified_by_user_id=verifier.id,
        verified_at=now - timedelta(minutes=30),
    )

    _auth_as_student(
        override_authenticated_user,
        user_id=student.id,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )

    response = client.get(
        f"/applications/{application.id}/checklist",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 3

    summary = compute_checklist_completeness(body["items"])

    assert summary.total_items == 3
    assert summary.required_items == 2
    assert summary.optional_items == 1
    assert summary.approved_count == 2
    assert summary.pending_count == 0
    assert summary.rejected_count == 0
    assert summary.missing_count == 0
    assert summary.is_complete is True
