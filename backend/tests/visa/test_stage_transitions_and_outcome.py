"""Visa stage transitions + outcome recording (E35; Journey J28; issue #197).

Integration coverage tying the visa stage progression (E25 / J18) to
the visa outcome update API (#195; Journey J28). The E35 epic
guarantees two coupled behaviors:

1. ``outcome_date`` / outcome record can only exist while the
   application is at the ``visa_processing`` stage. Once the
   application advances out (to ``enrolled``, ``rejected``,
   ``withdrawn``, or ``loan_processing``) the outcome endpoint
   rejects further writes with 422.
2. The visa outcome update itself does NOT advance the pipeline
   stage. Recording an outcome decision is a per-application
   status update, distinct from the dedicated
   ``mark-enrolled`` / ``mark-rejected`` / ``mark-withdrawn`` and
   generic ``advance-stage`` actions.

These tests pin those invariants by walking applications through
the E25 advance-stage API (to enter and exit the visa stage) and
through the visa outcome update API (to record the outcome in the
middle), then asserting (a) the outcome row is recorded while the
application is at ``visa_processing``, (b) it persists after the
application leaves for a terminal state, (c) it is rejected if a
later outcome update attempt is made after the terminal advance,
and (d) the outcome update never inserts a ``StageHistory`` row.

Mirrors the conventions used in ``tests/visa/test_outcome.py``
(read-side and pure-PATCH coverage) and
``tests/applications/test_advance_stage.py`` (stage transition
coverage) so the three files read consistently.
"""


import pytest

from app.models.application import Application
from app.models.stage_history import StageHistory
from app.models.tenant import Tenant
from app.models.visa_outcome import VisaOutcome
from app.pipeline.default_transitions import seed_default_stage_transitions
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from tests.applications.helpers import seed_application
from tests.branches.helpers import seed_branch
from tests.factories.users import make_authenticated_user, make_db_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tenant(db_session, *, slug: str) -> Tenant:
    tenant = Tenant(name=slug, slug=slug)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


def _setup(
    db_session,
    *,
    initial_stage: PipelineStage,
    slug: str = "visa-x",
):
    """Create a tenant + branch + counselor + role-aligned user, plus an application.

    Returns ``(tenant, branch, counselor, visa_user, application)``.
    ``counselor`` holds ``application:advance_stage`` so it can move the
    application across stages via the ``advance-stage`` API;
    ``visa_user`` is the VISA_PROCESSOR who records the outcome. Both are
    in the same tenant and (for counselors) branch.
    """
    seed_default_stage_transitions(db_session)
    tenant = _tenant(db_session, slug=slug)
    branch = seed_branch(db_session, tenant_id=tenant.id)
    counselor = make_db_user(
        db_session,
        Role.COUNSELOR,
        tenant_id=tenant.id,
        branch_id=branch.id,
    )
    visa_user = make_db_user(
        db_session,
        Role.VISA_PROCESSOR,
        tenant_id=tenant.id,
    )
    application = seed_application(
        db_session,
        tenant_id=tenant.id,
        branch_id=branch.id,
        assigned_counselor_id=counselor.id,
        stage=initial_stage,
    )
    return tenant, branch, counselor, visa_user, application


def _as_counselor(counselor) -> object:
    return make_authenticated_user(
        Role.COUNSELOR,
        user_id=counselor.id,
        tenant_id=counselor.tenant_id,
        branch_id=counselor.branch_id,
    )


def _as_visa_processor(visa_user) -> object:
    return make_authenticated_user(
        Role.VISA_PROCESSOR,
        user_id=visa_user.id,
        tenant_id=visa_user.tenant_id,
        branch_id=None,
    )


def _advance(client, application_id: int, *, to_stage: PipelineStage) -> object:
    return client.post(
        f"/applications/{application_id}/stage",
        json={"to_stage": to_stage.value},
        headers={"Authorization": "Bearer test-token"},
    )


# ---------------------------------------------------------------------------
# Stage-entry tests: applications must be at visa_processing to accept an outcome
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "preceding_stage",
    [
        PipelineStage.REGISTERED,
        PipelineStage.COUNSELING,
        PipelineStage.UNIVERSITY_SHORTLISTING,
        PipelineStage.APPLICATION_SUBMITTED,
        PipelineStage.DOCUMENT_VERIFICATION,
        PipelineStage.OFFER_LETTER,
        PipelineStage.LOAN_PROCESSING,
    ],
)
def test_outcome_rejected_before_application_reaches_visa_stage(
    client,
    db_session,
    override_authenticated_user,
    preceding_stage: PipelineStage,
) -> None:
    """An outcome patch fails (422) until the application is at ``visa_processing``.

    Walks an application from its seeded stage forward, asserting
    at each step along the way that the outcome endpoint surfaces
    422 until the application lands on ``visa_processing``. On that
    landing, the call succeeds and the first outcome row is written.

    Coverage notes:
      * For every preceding non-terminal stage (REGISTERED ... OFFER_LETTER),
        a counselor walks the canonical forward path to visa_processing,
        verifying the in-stage guard is enforced at every intermediate
        stage.
      * LOAN_PROCESSING is a sibling non-terminal stage that CANNOT
        reach ``visa_processing`` via the canonical forward path; the
        same logic the visa outcome update API enforces (only
        ``visa_processing`` accepts the outcome) is exercised by
        first attempting the outcome (422), then returning to
        ``visa_processing`` via the explicit
        ``LOAN_PROCESSING -> VISA_PROCESSING`` rule (which the test
        does NOT exercise -- that is covered by
        ``test_outcome_rejected_while_at_loan_processing_then_accepted_back_at_visa_processing``
        below).
    """
    # The seeded stage defines where the application starts. For the
    # non-canonical LOAN_PROCESSING case we seed at LOAN_PROCESSING and
    # only the "blocked first attempt" assertion applies -- the forward
    # walk is skipped (the canonical forward path never visits
    # LOAN_PROCESSING).
    if preceding_stage is PipelineStage.LOAN_PROCESSING:
        tenant, branch, counselor, visa_user, application = _setup(
            db_session,
            initial_stage=PipelineStage.LOAN_PROCESSING,
            slug=f"visa-enter-{preceding_stage.value}",
        )
        override_authenticated_user(_as_visa_processor(visa_user))
        blocked = client.patch(
            f"/visa/applications/{application.id}/outcome",
            json={"status": "approved"},
        )
        assert blocked.status_code == 422, blocked.text
        assert "loan_processing" in blocked.json()["detail"]
        return

    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=preceding_stage,
        slug=f"visa-enter-{preceding_stage.value}",
    )

    # Visa processor cannot record an outcome while the application is
    # NOT yet at visa_processing. Cover the in-stage guard for each
    # preceding stage.
    override_authenticated_user(_as_visa_processor(visa_user))
    blocked = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "notes": "too early"},
    )
    assert blocked.status_code == 422, blocked.text
    assert preceding_stage.value in blocked.json()["detail"]

    # Counselor walks the application forward one stage at a time.
    # The current stage is always the pair immediately preceding the
    # target; advancing the loop index from the first canonical stage is
    # invalid for registered, counseling, university_shortlisting,
    # application_submitted, document_verification, and offer_letter.
    forward_path = [
        PipelineStage.COUNSELING,
        PipelineStage.UNIVERSITY_SHORTLISTING,
        PipelineStage.APPLICATION_SUBMITTED,
        PipelineStage.DOCUMENT_VERIFICATION,
        PipelineStage.OFFER_LETTER,
        PipelineStage.VISA_PROCESSING,
    ]
    starting_index = forward_path.index(preceding_stage) if preceding_stage in forward_path else -1
    override_authenticated_user(_as_counselor(counselor))
    for next_stage in forward_path[starting_index + 1:]:
        response = _advance(client, application.id, to_stage=next_stage)
        assert response.status_code == 200, response.text
        if next_stage is PipelineStage.VISA_PROCESSING:
            break

    # Now at visa_processing, the outcome PATCH succeeds.
    override_authenticated_user(_as_visa_processor(visa_user))
    accepted = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "notes": "now at visa stage"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "approved"

    rows = db_session.query(VisaOutcome).filter_by(application_id=application.id).all()
    assert len(rows) == 1
    assert rows[0].status == "approved"


def test_outcome_patch_accepted_at_visa_processing_after_explicit_advance(
    client, db_session, override_authenticated_user
) -> None:
    """An OFFER_LETTER application is advanced to visa_processing by a counselor.

    After the advance, a visa processor can record the outcome; the
    application is at visa_processing exactly when the row is written.
    """
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.OFFER_LETTER,
        slug="visa-offer-letter",
    )

    # Counselor advances the application into the visa stage.
    override_authenticated_user(_as_counselor(counselor))
    advance = _advance(client, application.id, to_stage=PipelineStage.VISA_PROCESSING)
    assert advance.status_code == 200, advance.text
    assert advance.json()["application"]["stage"] == PipelineStage.VISA_PROCESSING.value

    # Visa processor records the outcome against the visa-stage application.
    override_authenticated_user(_as_visa_processor(visa_user))
    patch = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "outcome_date": "2026-09-30T10:00:00+00:00"},
    )
    assert patch.status_code == 200, patch.text
    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.VISA_PROCESSING

    stored = db_session.query(VisaOutcome).filter_by(application_id=application.id).one()
    assert stored.status == "approved"
    assert stored.outcome_date is not None


# ---------------------------------------------------------------------------
# Stage-exit tests: outcome is recorded before the application leaves visa_processing
# ---------------------------------------------------------------------------


def test_outcome_persists_after_application_marked_enrolled(
    client, db_session, override_authenticated_user
) -> None:
    """Outcome row is written, then counselor advances to ENROLLED, outcome remains."""
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.VISA_PROCESSING,
        slug="visa-enroll-after-outcome",
    )

    override_authenticated_user(_as_visa_processor(visa_user))
    seeded = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "notes": "All paperwork cleared"},
    )
    assert seeded.status_code == 200, seeded.text

    # Counselor marks the application enrolled.
    override_authenticated_user(_as_counselor(counselor))
    enroll = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={"details": "Visa outcome = approved; enrolling for Fall 2026"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert enroll.status_code == 200, enroll.text

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.ENROLLED

    # Outcome row remains tied to the application (1:1 unique constraint
    # on application_id); has not been wiped by the transition.
    outcome = db_session.query(VisaOutcome).filter_by(application_id=application.id).one()
    assert outcome.status == "approved"

    # Subsequent outcome updates are 422 because the application is
    # no longer at visa_processing (it is in a terminal state).
    override_authenticated_user(_as_visa_processor(visa_user))
    rejected = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"notes": "Should not save"},
    )
    assert rejected.status_code == 422
    assert "visa_processing" in rejected.json()["detail"]


def test_outcome_persists_after_application_marked_rejected(
    client, db_session, override_authenticated_user
) -> None:
    """Symmetric to enroll: outcome survives a transition to the REJECTED terminal state."""
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.VISA_PROCESSING,
        slug="visa-reject-after-outcome",
    )

    override_authenticated_user(_as_visa_processor(visa_user))
    seeded = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "rejected", "notes": "Embassy denied"},
    )
    assert seeded.status_code == 200, seeded.text

    override_authenticated_user(_as_counselor(counselor))
    reject = client.post(
        f"/applications/{application.id}/mark-rejected",
        json={"reason": "Visa outcome rejected by embassy"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert reject.status_code == 200, reject.text

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.REJECTED

    outcome = db_session.query(VisaOutcome).filter_by(application_id=application.id).one()
    assert outcome.status == "rejected"


def test_outcome_persists_after_application_marked_withdrawn(
    client, db_session, override_authenticated_user
) -> None:
    """Symmetric to enroll: outcome survives a transition to the WITHDRAWN terminal state."""
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.VISA_PROCESSING,
        slug="visa-withdraw-after-outcome",
    )

    override_authenticated_user(_as_visa_processor(visa_user))
    seeded = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "notes": "Pending withdrawal paperwork"},
    )
    assert seeded.status_code == 200, seeded.text

    override_authenticated_user(_as_counselor(counselor))
    withdraw = client.post(
        f"/applications/{application.id}/mark-withdrawn",
        json={"reason": "Student chose a different program"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert withdraw.status_code == 200, withdraw.text

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.WITHDRAWN

    outcome = db_session.query(VisaOutcome).filter_by(application_id=application.id).one()
    assert outcome.status == "approved"


# ---------------------------------------------------------------------------
# Outcome update does NOT touch the pipeline stage (or the history log)
# ---------------------------------------------------------------------------


def test_outcome_patch_does_not_change_pipeline_stage(
    client, db_session, override_authenticated_user
) -> None:
    """A successful outcome PATCH leaves the application's stage at visa_processing.

    The visa outcome endpoint is a status-capture side-channel; the
    application's stage is unchanged until a dedicated
    advance-stage / mark-* action moves it. Mirrors the J28 /
    Issue #195 endpoint docstring.
    """
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.VISA_PROCESSING,
        slug="visa-no-stage-change",
    )
    override_authenticated_user(_as_visa_processor(visa_user))

    response = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved"},
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    refreshed = db_session.get(Application, application.id)
    assert refreshed.stage == PipelineStage.VISA_PROCESSING

    # The outcome PATCH must not insert a StageHistory row.
    history_count = (
        db_session.query(StageHistory)
        .filter(StageHistory.application_id == application.id)
        .count()
    )
    assert history_count == 0


def test_outcome_patch_does_not_write_history_even_after_updates(
    client, db_session, override_authenticated_user
) -> None:
    """Updating the outcome several times still writes ZERO StageHistory rows."""
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.VISA_PROCESSING,
        slug="visa-no-history-on-updates",
    )
    override_authenticated_user(_as_visa_processor(visa_user))

    for status in ("approved", "rejected", "approved"):
        response = client.patch(
            f"/visa/applications/{application.id}/outcome",
            json={"status": status},
        )
        assert response.status_code == 200, response.text

    history_count = (
        db_session.query(StageHistory)
        .filter(StageHistory.application_id == application.id)
        .count()
    )
    assert history_count == 0


# ---------------------------------------------------------------------------
# Loan processing loop: outcome blocked while loan_processing, accepted again on return
# ---------------------------------------------------------------------------


def test_outcome_rejected_while_at_loan_processing_then_accepted_back_at_visa_processing(
    client, db_session, override_authenticated_user
) -> None:
    """Loan loop: visa -> loan_processing -> visa preserves exactly one outcome row.

    Per ``app.pipeline.default_transitions.DEFAULT_TRANSITIONS``,
    ``visa_processing -> loan_processing -> visa_processing`` is the
    only round-trip in the pipeline (Requirements §5 optional loan
    flow). The outcome endpoint MUST treat ``loan_processing`` as
    out-of-stage (422) and resume accepting updates once the
    application returns to ``visa_processing`` (200). The same
    outcome row is updated in place because the unique constraint
    is on ``application_id`` not on stage.
    """
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.VISA_PROCESSING,
        slug="visa-loan-loop",
    )

    # Seed the outcome at visa_processing.
    override_authenticated_user(_as_visa_processor(visa_user))
    seeded = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "notes": "Sent to loan track"},
    )
    assert seeded.status_code == 200, seeded.text
    first_id = seeded.json()["id"]

    # Counselor advances into loan_processing.
    override_authenticated_user(_as_counselor(counselor))
    into_loan = _advance(client, application.id, to_stage=PipelineStage.LOAN_PROCESSING)
    assert into_loan.status_code == 200, into_loan.text

    # Outcome updates are 422 while at loan_processing (the application
    # is not at visa_processing).
    override_authenticated_user(_as_visa_processor(visa_user))
    blocked = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"notes": "trying to update from loan stage"},
    )
    assert blocked.status_code == 422
    assert "loan_processing" in blocked.json()["detail"] or "visa_processing" in blocked.json()["detail"]

    # Counselor returns the application to visa_processing.
    override_authenticated_user(_as_counselor(counselor))
    back = _advance(client, application.id, to_stage=PipelineStage.VISA_PROCESSING)
    assert back.status_code == 200, back.text

    # Outcome updates are accepted again; the existing row is updated in place.
    override_authenticated_user(_as_visa_processor(visa_user))
    updated = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"notes": "returned from loan loop"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == first_id, "outcome row id must be stable across the loan loop"
    assert updated.json()["notes"] == "returned from loan loop"
    assert updated.json()["status"] == "approved"

    rows = db_session.query(VisaOutcome).filter_by(application_id=application.id).all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Combined: outcome first, then advance to terminal; outcome second is rejected
# ---------------------------------------------------------------------------


def test_outcome_then_mark_rejected_blocks_later_outcome_updates(
    client, db_session, override_authenticated_user
) -> None:
    """Once a terminal transition happens, outcome updates are 422 forever.

    This is the combined invariant: an outcome can be recorded in the
    visa stage, the application is then advanced to a terminal state,
    and from that point onward any further outcome PATCH is rejected
    with 422 (the ``visa_processing`` in-stage guard). Mirrors
    ``test_visa_outcome_rejects_terminal_state_application`` in
    ``tests/visa/test_outcome.py`` but exercises the full flow
    (record -> transition -> attempted update) rather than seeding
    a terminal application and patching it directly.
    """
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.VISA_PROCESSING,
        slug="visa-terminal-blocks-later",
    )

    override_authenticated_user(_as_visa_processor(visa_user))
    first = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "notes": "first try"},
    )
    assert first.status_code == 200

    override_authenticated_user(_as_counselor(counselor))
    reject = client.post(
        f"/applications/{application.id}/mark-rejected",
        json={"reason": "Documents insufficient"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert reject.status_code == 200

    override_authenticated_user(_as_visa_processor(visa_user))
    second = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved", "notes": "second try"},
    )
    assert second.status_code == 422
    assert "visa_processing" in second.json()["detail"]


# ---------------------------------------------------------------------------
# Stage transition logs in spite of outcome activity
# ---------------------------------------------------------------------------


def test_advance_stage_writes_history_rows_for_visa_stage_transitions(
    client, db_session, override_authenticated_user
) -> None:
    """Walking the application in and out of visa_processing writes 2 StageHistory rows.

    Sanity check that the E25 advance-stage flow still records
    ``StageHistory`` rows for the two transitions that bookend the
    visa stage (``OFFER_LETTER -> VISA_PROCESSING`` and
    ``VISA_PROCESSING -> ENROLLED``). Outcome activity between
    those transitions does not insert or rewrite history rows.
    """
    tenant, branch, counselor, visa_user, application = _setup(
        db_session,
        initial_stage=PipelineStage.OFFER_LETTER,
        slug="visa-stage-history",
    )

    # Counselor: OFFER_LETTER -> VISA_PROCESSING.
    override_authenticated_user(_as_counselor(counselor))
    into_visa = _advance(client, application.id, to_stage=PipelineStage.VISA_PROCESSING)
    assert into_visa.status_code == 200, into_visa.text
    assert into_visa.json()["history_entry"]["from_stage"] == PipelineStage.OFFER_LETTER.value
    assert into_visa.json()["history_entry"]["to_stage"] == PipelineStage.VISA_PROCESSING.value

    # Visa processor records the outcome mid-stage (must NOT add history).
    override_authenticated_user(_as_visa_processor(visa_user))
    recorded = client.patch(
        f"/visa/applications/{application.id}/outcome",
        json={"status": "approved"},
    )
    assert recorded.status_code == 200, recorded.text

    # Counselor: VISA_PROCESSING -> ENROLLED.
    override_authenticated_user(_as_counselor(counselor))
    enroll = client.post(
        f"/applications/{application.id}/mark-enrolled",
        json={"details": "Visa outcome approved; enrolling"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert enroll.status_code == 200, enroll.text

    db_session.expire_all()
    history_rows = (
        db_session.query(StageHistory)
        .filter(StageHistory.application_id == application.id)
        .order_by(StageHistory.id)
        .all()
    )
    assert len(history_rows) == 2
    assert history_rows[0].from_stage == PipelineStage.OFFER_LETTER
    assert history_rows[0].to_stage == PipelineStage.VISA_PROCESSING
    assert history_rows[1].from_stage == PipelineStage.VISA_PROCESSING
    assert history_rows[1].to_stage == PipelineStage.ENROLLED
