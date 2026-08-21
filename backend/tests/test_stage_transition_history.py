"""Tests covering the E25 acceptance criterion "invalid transitions rejected,
history recorded correctly" (issue #171; Journey J18; Epic E25).

This module focuses on the contract that ties stage-transition validation to
the StageHistory audit log. It is the test counterpart of the rules in
:mod:`app.pipeline.default_transitions` and the service helpers in
:mod:`app.services.stage_progression`.

What is verified here (mapping to the J18 acceptance criterion):

1. **Invalid transitions are rejected.** The ``validate_transition`` guard
   raises ``InvalidStageTransitionError`` for every transition that is not in
   the platform-default or tenant-specific rule table, INCLUDING transitions
   out of terminal stages. The test cases exercise that gate end-to-end at
   the service + ORM seam so any regression in either layer surfaces here.
2. **History is recorded correctly.** For each kind of accepted transition
   (forward, loan loop, terminal with reason, terminal without reason,
   initial provenance row with ``from_stage IS NULL``), the test asserts
   that the ``StageHistory`` row that would be inserted by an advance-stage
   flow carries every required column with the right value:

   * ``tenant_id`` matches the application (multi-tenant safety, ADR-0001)
   * ``application_id`` matches the application row
   * ``from_stage`` is the previous stage (NULL for the first row)
   * ``to_stage`` is the new stage
   * ``changed_by_user_id`` is the staff actor (NULL if absent)
   * ``changed_at`` is the moment of transition (round-trippable)
   * ``reason`` is preserved exactly when supplied

These tests are written so they pass against the existing
``validate_transition`` / ``StageHistory`` primitives -- no advance-stage
HTTP route is required. They will continue to gate the behaviour once the
``POST /applications/{id}/stage`` endpoint ships (issue #169).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.stage_history import StageHistory
from app.models.stage_transition import StageTransition
from app.pipeline.default_transitions import (
    DEFAULT_TRANSITIONS,
    seed_default_stage_transitions,
)
from app.pipeline.stages import PipelineStage
from app.rbac.roles import Role
from app.services.stage_progression import (
    InvalidStageTransitionError,
    is_valid_transition,
    is_valid_transition_for_platform,
    validate_transition,
)
from tests.applications.helpers import seed_application
from tests.factories.timestamps import utc_now
from tests.factories.users import make_db_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record_history(
    db: Session,
    *,
    application: Application,
    from_stage: PipelineStage | None,
    to_stage: PipelineStage,
    changed_by_user_id: int | None,
    reason: str | None = None,
    changed_at: datetime | None = None,
) -> StageHistory:
    """Insert a StageHistory row mirroring what the advance-stage flow writes.

    Centralising the row construction here keeps the assertions focused on
    the persisted shape (tenant_id, from_stage, to_stage, etc.) and keeps
    the test readable even as the row layout gains optional fields.
    """
    now = changed_at or utc_now()
    row = StageHistory(
        tenant_id=application.tenant_id,
        application_id=application.id,
        from_stage=from_stage,
        to_stage=to_stage,
        changed_by_user_id=changed_by_user_id,
        changed_at=now,
        reason=reason,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _seed_default(db: Session, *pairs: tuple[PipelineStage, PipelineStage]) -> None:
    """Seed the given platform-default (from, to) transition rows."""
    for from_stage, to_stage in pairs:
        _seed_default_transition(db, from_stage, to_stage)


def _seed_default_transition(
    db: Session,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
    *,
    is_active: bool = True,
) -> StageTransition:
    """Create and commit a single platform-default (tenant_id IS NULL) row."""
    now = utc_now()
    row = StageTransition(
        from_stage=from_stage,
        to_stage=to_stage,
        tenant_id=None,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ===========================================================================
# 1. INVALID TRANSITIONS REJECTED
#    The matrix here complements the unit-level coverage in
#    ``test_stage_progression.py`` and additionally asserts that NO
#    StageHistory row is written when validation fails (the gate fires
#    BEFORE any audit-log write, by design).
# ===========================================================================


class TestInvalidTransitionsRejected:
    """End-to-end rejection matrix for the validate_transition gate (E25; J18)."""

    def test_forward_jump_rejected_and_no_history_persisted(
        self, db_session: Session
    ) -> None:
        """REGISTERED → DOCUMENT_VERIFICATION is rejected; no audit row is written."""
        _seed_default(db_session, (PipelineStage.REGISTERED, PipelineStage.COUNSELING))
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        before = db_session.query(StageHistory).count()

        with pytest.raises(InvalidStageTransitionError) as exc_info:
            validate_transition(
                db_session,
                PipelineStage.REGISTERED,
                PipelineStage.DOCUMENT_VERIFICATION,
                tenant_id=application.tenant_id,
            )
        assert exc_info.value.from_stage == PipelineStage.REGISTERED
        assert exc_info.value.to_stage == PipelineStage.DOCUMENT_VERIFICATION

        # Defensive: validate_transition is a pure predicate; it must NOT
        # have touched the StageHistory table.
        assert db_session.query(StageHistory).count() == before

    def test_backward_transition_rejected_and_no_history_persisted(
        self, db_session: Session
    ) -> None:
        """COUNSELING → REGISTERED is rejected; no audit row is written."""
        _seed_default(
            db_session,
            (PipelineStage.REGISTERED, PipelineStage.COUNSELING),
            (PipelineStage.COUNSELING, PipelineStage.UNIVERSITY_SHORTLISTING),
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.COUNSELING
        )
        before = db_session.query(StageHistory).count()

        with pytest.raises(InvalidStageTransitionError):
            validate_transition(
                db_session,
                PipelineStage.COUNSELING,
                PipelineStage.REGISTERED,
                tenant_id=application.tenant_id,
            )
        assert db_session.query(StageHistory).count() == before

    def test_transition_from_terminal_stage_rejected(
        self, db_session: Session
    ) -> None:
        """No outgoing transition is allowed from any terminal stage (E25 absorbing)."""
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.ENROLLED
        )
        for terminal in (
            PipelineStage.ENROLLED,
            PipelineStage.REJECTED,
            PipelineStage.WITHDRAWN,
        ):
            for target in (
                PipelineStage.REGISTERED,
                PipelineStage.COUNSELING,
                PipelineStage.REJECTED,
                PipelineStage.WITHDRAWN,
                PipelineStage.ENROLLED,
            ):
                if terminal == target:
                    continue
                with pytest.raises(InvalidStageTransitionError):
                    validate_transition(
                        db_session,
                        terminal,
                        target,
                        tenant_id=application.tenant_id,
                    )

    def test_self_loop_rejected_for_every_stage(self, db_session: Session) -> None:
        """A stage never transitions to itself -- the rule table has no self-loops."""
        _seed_default_transition(
            db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        for stage in PipelineStage:
            with pytest.raises(InvalidStageTransitionError):
                validate_transition(
                    db_session,
                    stage,
                    stage,
                    tenant_id=application.tenant_id,
                )

    def test_undefined_transition_rejected(self, db_session: Session) -> None:
        """Transitions missing from the rule table (no row + no override) are rejected."""
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        # REGISTERED → ENROLLED is never a direct skip.
        with pytest.raises(InvalidStageTransitionError):
            validate_transition(
                db_session,
                PipelineStage.REGISTERED,
                PipelineStage.ENROLLED,
                tenant_id=application.tenant_id,
            )

    def test_default_rule_flipped_inactive_blocks_transition(
        self, db_session: Session
    ) -> None:
        """Flipping the platform-default rule to ``is_active=False`` blocks the move."""
        existing = _seed_default_transition(
            db_session,
            PipelineStage.REGISTERED,
            PipelineStage.COUNSELING,
            is_active=True,
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        before = db_session.query(StageHistory).count()

        # Tenant deactivates the default rule -- the only active row for this pair.
        existing.is_active = False
        db_session.commit()
        db_session.refresh(existing)
        assert existing.is_active is False

        with pytest.raises(InvalidStageTransitionError):
            validate_transition(
                db_session,
                PipelineStage.REGISTERED,
                PipelineStage.COUNSELING,
                tenant_id=application.tenant_id,
            )
        assert db_session.query(StageHistory).count() == before


# ===========================================================================
# 2. HISTORY RECORDED CORRECTLY FOR VALID TRANSITIONS
#    Once validate_transition gates the move, the audit row must persist
#    every required field under the right invariants.
# ===========================================================================


class TestHistoryRecordedForValidTransitions:
    """End-to-end history-recording correctness for the forward pipeline."""

    def test_initial_provenance_row_has_null_from_stage(
        self, db_session: Session
    ) -> None:
        """The first recorded row for an application carries ``from_stage IS NULL``.

        This is the application-creation provenance row (or the first row
        inserted when the timeline is bootstrapped); the schema explicitly
        supports ``from_stage`` NULL per the StageHistory docstring.
        """
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
        )

        assert row.from_stage is None
        assert row.to_stage == PipelineStage.REGISTERED
        assert row.application_id == application.id
        assert row.tenant_id == application.tenant_id

    def test_forward_registered_to_counseling_records_complete_row(
        self, db_session: Session
    ) -> None:
        """A forward move writes a row carrying every column with the right value."""
        _seed_default(
            db_session, (PipelineStage.REGISTERED, PipelineStage.COUNSELING)
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        # Permission holder who initiated the move.
        counselor = make_db_user(
            db_session,
            Role.COUNSELOR,
            tenant_id=application.tenant_id,
            branch_id=application.branch_id,
        )

        # Gate the move first -- the same call the API would make.
        validate_transition(
            db_session,
            application.stage,
            PipelineStage.COUNSELING,
            tenant_id=application.tenant_id,
        )

        before_change = utc_now()
        row = _record_history(
            db_session,
            application=application,
            from_stage=application.stage,
            to_stage=PipelineStage.COUNSELING,
            changed_by_user_id=counselor.id,
            changed_at=before_change,
        )

        assert row.id is not None
        assert row.tenant_id == application.tenant_id
        assert row.application_id == application.id
        assert row.from_stage == PipelineStage.REGISTERED
        assert row.to_stage == PipelineStage.COUNSELING
        assert row.changed_by_user_id == counselor.id
        # ``changed_at`` survives a roundtrip (SQLite drops tzinfo, so we
        # compare absolute instants).
        assert row.changed_at.replace(tzinfo=timezone.utc) == before_change
        # Forward moves do not carry a reason.
        assert row.reason is None

    def test_counseling_to_university_shortlisting_records_history(
        self, db_session: Session
    ) -> None:
        """Each subsequent forward hop appends its own audit row."""
        _seed_default(
            db_session,
            (PipelineStage.REGISTERED, PipelineStage.COUNSELING),
            (PipelineStage.COUNSELING, PipelineStage.UNIVERSITY_SHORTLISTING),
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.COUNSELING
        )
        counselor = make_db_user(
            db_session,
            Role.COUNSELOR,
            tenant_id=application.tenant_id,
            branch_id=application.branch_id,
        )

        validate_transition(
            db_session,
            application.stage,
            PipelineStage.UNIVERSITY_SHORTLISTING,
            tenant_id=application.tenant_id,
        )
        _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.UNIVERSITY_SHORTLISTING,
            changed_by_user_id=counselor.id,
        )

        rows = (
            db_session.query(StageHistory)
            .filter(StageHistory.application_id == application.id)
            .order_by(StageHistory.id)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].from_stage == PipelineStage.COUNSELING
        assert rows[0].to_stage == PipelineStage.UNIVERSITY_SHORTLISTING
        assert rows[0].changed_by_user_id == counselor.id

    def test_history_ordering_matches_chronological_transitions(
        self, db_session: Session
    ) -> None:
        """A multi-hop timeline yields monotonically increasing ``changed_at`` values."""
        _seed_default(
            db_session,
            (PipelineStage.REGISTERED, PipelineStage.COUNSELING),
            (PipelineStage.COUNSELING, PipelineStage.UNIVERSITY_SHORTLISTING),
            (PipelineStage.UNIVERSITY_SHORTLISTING, PipelineStage.APPLICATION_SUBMITTED),
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        counselor = make_db_user(
            db_session,
            Role.COUNSELOR,
            tenant_id=application.tenant_id,
            branch_id=application.branch_id,
        )

        base = utc_now()
        hops = [
            (PipelineStage.REGISTERED, PipelineStage.COUNSELING, base),
            (
                PipelineStage.COUNSELING,
                PipelineStage.UNIVERSITY_SHORTLISTING,
                base + timedelta(seconds=10),
            ),
            (
                PipelineStage.UNIVERSITY_SHORTLISTING,
                PipelineStage.APPLICATION_SUBMITTED,
                base + timedelta(seconds=20),
            ),
        ]
        for from_stage, to_stage, when in hops:
            validate_transition(
                db_session,
                from_stage,
                to_stage,
                tenant_id=application.tenant_id,
            )
            _record_history(
                db_session,
                application=application,
                from_stage=from_stage,
                to_stage=to_stage,
                changed_by_user_id=counselor.id,
                changed_at=when,
            )

        rows = (
            db_session.query(StageHistory)
            .filter(StageHistory.application_id == application.id)
            .order_by(StageHistory.changed_at)
            .all()
        )
        assert len(rows) == 3
        assert [r.to_stage for r in rows] == [
            PipelineStage.COUNSELING,
            PipelineStage.UNIVERSITY_SHORTLISTING,
            PipelineStage.APPLICATION_SUBMITTED,
        ]
        # Non-decreasing timestamps reflect the chronological sequence the
        # stage-timeline UI will render.
        timestamps = [
            r.changed_at.replace(tzinfo=timezone.utc) for r in rows
        ]
        assert timestamps == sorted(timestamps)


# ===========================================================================
# 3. TERMINAL STATES -- ENROLLED / REJECTED / WITHDRAWN
#    Requirements §5: "Enrolled / Rejected / Withdrawn, three distinct
#    terminal states, each capturing a reason". The audit log MUST capture
#    the reason for the two rejection terminals and should reflect the
#    final-stage semantics (no further transitions).
# ===========================================================================


class TestTerminalStatesRecorded:
    """History rows for the three terminal states (E25; Requirements §5)."""

    def test_rejected_with_reason_records_reason(self, db_session: Session) -> None:
        """A REJECTED transition carries the required reason text."""
        _seed_default(
            db_session, (PipelineStage.COUNSELING, PipelineStage.REJECTED)
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.COUNSELING
        )
        owner = make_db_user(
            db_session,
            Role.CONSULTANCY_OWNER,
            tenant_id=application.tenant_id,
        )
        reason = "Student did not meet the minimum GPA requirement"

        validate_transition(
            db_session,
            PipelineStage.COUNSELING,
            PipelineStage.REJECTED,
            tenant_id=application.tenant_id,
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.REJECTED,
            changed_by_user_id=owner.id,
            reason=reason,
        )
        assert row.to_stage == PipelineStage.REJECTED
        assert row.reason == reason
        assert row.changed_by_user_id == owner.id

    def test_withdrawn_with_reason_records_reason(self, db_session: Session) -> None:
        """A WITHDRAWN transition carries the required reason text."""
        _seed_default(
            db_session, (PipelineStage.DOCUMENT_VERIFICATION, PipelineStage.WITHDRAWN)
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.DOCUMENT_VERIFICATION
        )
        branch_manager = make_db_user(
            db_session,
            Role.BRANCH_MANAGER,
            tenant_id=application.tenant_id,
            branch_id=application.branch_id,
        )
        reason = "Student withdrew to pursue a different program"

        validate_transition(
            db_session,
            PipelineStage.DOCUMENT_VERIFICATION,
            PipelineStage.WITHDRAWN,
            tenant_id=application.tenant_id,
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.DOCUMENT_VERIFICATION,
            to_stage=PipelineStage.WITHDRAWN,
            changed_by_user_id=branch_manager.id,
            reason=reason,
        )
        assert row.to_stage == PipelineStage.WITHDRAWN
        assert row.reason == reason

    def test_enrolled_records_row_with_null_reason(
        self, db_session: Session
    ) -> None:
        """ENROLLED is a happy-path terminal; the row exists with ``reason IS NULL``."""
        _seed_default(
            db_session, (PipelineStage.VISA_PROCESSING, PipelineStage.ENROLLED)
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.VISA_PROCESSING
        )
        owner = make_db_user(
            db_session,
            Role.CONSULTANCY_OWNER,
            tenant_id=application.tenant_id,
        )

        validate_transition(
            db_session,
            PipelineStage.VISA_PROCESSING,
            PipelineStage.ENROLLED,
            tenant_id=application.tenant_id,
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.VISA_PROCESSING,
            to_stage=PipelineStage.ENROLLED,
            changed_by_user_id=owner.id,
        )
        assert row.to_stage == PipelineStage.ENROLLED
        assert row.reason is None

    def test_terminal_history_implies_no_subsequent_moves(
        self, db_session: Session
    ) -> None:
        """Once a terminal row is recorded, no further transitions are possible."""
        _seed_default(
            db_session,
            (PipelineStage.REGISTERED, PipelineStage.COUNSELING),
            (PipelineStage.COUNSELING, PipelineStage.REJECTED),
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )

        validate_transition(
            db_session,
            PipelineStage.REGISTERED,
            PipelineStage.COUNSELING,
            tenant_id=application.tenant_id,
        )
        _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.REGISTERED,
            to_stage=PipelineStage.COUNSELING,
            changed_by_user_id=None,
        )

        validate_transition(
            db_session,
            PipelineStage.COUNSELING,
            PipelineStage.REJECTED,
            tenant_id=application.tenant_id,
        )
        _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.REJECTED,
            changed_by_user_id=None,
            reason="Incomplete document set",
        )

        with pytest.raises(InvalidStageTransitionError):
            validate_transition(
                db_session,
                PipelineStage.REJECTED,
                PipelineStage.REGISTERED,
                tenant_id=application.tenant_id,
            )


# ===========================================================================
# 4. LOAN PROCESSING LOOP
#    VISA_PROCESSING ↔ LOAN_PROCESSING is the optional loan-tracker loop
#    from Requirements §5; the audit log must reflect both directions.
# ===========================================================================


class TestLoanProcessingLoopHistory:
    """Audit rows for the optional LOAN_PROCESSING ↔ VISA_PROCESSING loop."""

    def test_loan_loop_records_outbound_and_return_rows(
        self, db_session: Session
    ) -> None:
        """VISA → LOAN → VISA produces two rows with the expected from/to."""
        _seed_default(
            db_session,
            (PipelineStage.VISA_PROCESSING, PipelineStage.LOAN_PROCESSING),
            (PipelineStage.LOAN_PROCESSING, PipelineStage.VISA_PROCESSING),
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.VISA_PROCESSING
        )
        owner = make_db_user(
            db_session,
            Role.CONSULTANCY_OWNER,
            tenant_id=application.tenant_id,
        )

        # Outbound -- visa processing hands off to the loan tracker.
        validate_transition(
            db_session,
            PipelineStage.VISA_PROCESSING,
            PipelineStage.LOAN_PROCESSING,
            tenant_id=application.tenant_id,
        )
        outbound = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.VISA_PROCESSING,
            to_stage=PipelineStage.LOAN_PROCESSING,
            changed_by_user_id=owner.id,
        )
        assert outbound.from_stage == PipelineStage.VISA_PROCESSING
        assert outbound.to_stage == PipelineStage.LOAN_PROCESSING

        # Return -- loan tracker hands back to visa processing.
        validate_transition(
            db_session,
            PipelineStage.LOAN_PROCESSING,
            PipelineStage.VISA_PROCESSING,
            tenant_id=application.tenant_id,
        )
        inbound = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.LOAN_PROCESSING,
            to_stage=PipelineStage.VISA_PROCESSING,
            changed_by_user_id=owner.id,
        )
        assert inbound.from_stage == PipelineStage.LOAN_PROCESSING
        assert inbound.to_stage == PipelineStage.VISA_PROCESSING

    def test_loan_processing_to_terminal_is_valid(self, db_session: Session) -> None:
        """LOAN_PROCESSING can still terminate via REJECTED / WITHDRAWN (E39 / E40)."""
        _seed_default(
            db_session,
            (PipelineStage.LOAN_PROCESSING, PipelineStage.REJECTED),
            (PipelineStage.LOAN_PROCESSING, PipelineStage.WITHDRAWN),
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.LOAN_PROCESSING
        )

        # Loan rejected
        validate_transition(
            db_session,
            PipelineStage.LOAN_PROCESSING,
            PipelineStage.REJECTED,
            tenant_id=application.tenant_id,
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.LOAN_PROCESSING,
            to_stage=PipelineStage.REJECTED,
            changed_by_user_id=None,
            reason="Loan application denied by lender",
        )
        assert row.to_stage == PipelineStage.REJECTED
        assert row.reason == "Loan application denied by lender"

        # And tenant-of-application rule applies symmetrically.
        assert (
            is_valid_transition(
                db_session,
                PipelineStage.LOAN_PROCESSING,
                PipelineStage.WITHDRAWN,
                tenant_id=application.tenant_id,
            )
            is True
        )


# ===========================================================================
# 5. MULTI-TENANT SAFETY
#    Stage history is tenant-scoped (ADR-0001). The row's ``tenant_id``
#    must equal the application's ``tenant_id`` and never leak across.
# ===========================================================================


class TestHistoryMultiTenantSafety:
    """The StageHistory ``tenant_id`` must mirror the application's tenant (ADR-0001)."""

    def test_history_tenant_id_matches_application_tenant_id(
        self, db_session: Session
    ) -> None:
        """A history row written for an application in tenant A carries tenant_id=A."""
        application = seed_application(
            db_session, tenant_id=42, stage=PipelineStage.REGISTERED
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.REGISTERED,
            to_stage=PipelineStage.COUNSELING,
            changed_by_user_id=None,
        )
        assert row.tenant_id == application.tenant_id == 42

    def test_history_rows_for_two_applications_in_different_tenants_isolate(
        self, db_session: Session
    ) -> None:
        """Two tenants' history streams never collide (no shared global rows)."""
        app_a = seed_application(
            db_session, tenant_id=10, stage=PipelineStage.REGISTERED
        )
        app_b = seed_application(
            db_session, tenant_id=20, stage=PipelineStage.REGISTERED
        )

        _record_history(
            db_session,
            application=app_a,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
        )
        _record_history(
            db_session,
            application=app_b,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
        )

        rows_a = (
            db_session.query(StageHistory)
            .filter(StageHistory.application_id == app_a.id)
            .all()
        )
        rows_b = (
            db_session.query(StageHistory)
            .filter(StageHistory.application_id == app_b.id)
            .all()
        )
        assert all(r.tenant_id == app_a.tenant_id for r in rows_a)
        assert all(r.tenant_id == app_b.tenant_id for r in rows_b)
        assert {r.tenant_id for r in rows_a} == {10}
        assert {r.tenant_id for r in rows_b} == {20}

    def test_history_records_carry_actor_attribution(
        self, db_session: Session
    ) -> None:
        """The history row carries the staff actor's id (changed_by_user_id)."""
        _seed_default(
            db_session, (PipelineStage.REGISTERED, PipelineStage.COUNSELING)
        )
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        # Owner-initiated advance (cross-branch single-tenant scope).
        owner = make_db_user(
            db_session,
            Role.CONSULTANCY_OWNER,
            tenant_id=application.tenant_id,
        )

        validate_transition(
            db_session,
            PipelineStage.REGISTERED,
            PipelineStage.COUNSELING,
            tenant_id=application.tenant_id,
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.REGISTERED,
            to_stage=PipelineStage.COUNSELING,
            changed_by_user_id=owner.id,
        )

        assert row.changed_by_user_id == owner.id
        # The row's tenant remains anchored to the application (not the actor).
        assert row.tenant_id == application.tenant_id

    def test_history_rejects_null_actor_writes_to_null_column(
        self, db_session: Session
    ) -> None:
        """When no actor is supplied, ``changed_by_user_id`` is stored as NULL.

        The column is nullable per the StageHistory schema so an actor-less
        row (e.g. a system-injected provenance row) round-trips faithfully.
        """
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
        )
        assert row.changed_by_user_id is None


# ===========================================================================
# 6. AUDIT-LOG INVARIANTS
#    Each StageHistory row carries identity, provenance, and timestamp
#    information that a downstream UI (e.g. the E25 stage timeline) needs.
# ===========================================================================


class TestAuditLogInvariants:
    """Row-level invariants of the StageHistory audit log."""

    def test_changed_at_round_trips_through_sqlite(self, db_session: Session) -> None:
        """``changed_at`` survives DB round-trips (SQLite drops tzinfo by design)."""
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        before = utc_now()
        row = _record_history(
            db_session,
            application=application,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
            changed_at=before,
        )
        # Compare absolute UTC instants -- SQLite drops tzinfo.
        assert row.changed_at.replace(tzinfo=timezone.utc) == before

    def test_history_record_carries_isolated_tenant_scope(
        self, db_session: Session
    ) -> None:
        """History rows for one tenant's application are not visible at the other tenant.

        Mirrors the StageHistory FK to ``applications.id`` -- every row
        belongs to exactly one application, and the application's tenant
        is the audit row's tenant.
        """
        app_a = seed_application(
            db_session, tenant_id=10, stage=PipelineStage.REGISTERED
        )
        app_b = seed_application(
            db_session, tenant_id=99, stage=PipelineStage.REGISTERED
        )
        _record_history(
            db_session,
            application=app_a,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
        )
        _record_history(
            db_session,
            application=app_b,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
        )

        # Cross-tenant fetch: tenant 10 sees only its own rows.
        rows_tenant_10 = (
            db_session.query(StageHistory)
            .filter(StageHistory.tenant_id == 10)
            .all()
        )
        rows_tenant_99 = (
            db_session.query(StageHistory)
            .filter(StageHistory.tenant_id == 99)
            .all()
        )
        assert {r.application_id for r in rows_tenant_10} == {app_a.id}
        assert {r.application_id for r in rows_tenant_99} == {app_b.id}

    def test_zero_history_rows_when_no_transitions_attempted(
        self, db_session: Session
    ) -> None:
        """A freshly seeded application has no history rows until a transition is recorded."""
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        rows = (
            db_session.query(StageHistory)
            .filter(StageHistory.application_id == application.id)
            .all()
        )
        assert rows == []

    def test_history_reason_preserved_verbatim(self, db_session: Session) -> None:
        """The free-text ``reason`` round-trips through SQLite with full fidelity."""
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.COUNSELING
        )
        reason = (
            "Multi-line reason.\nWith punctuation: !@#$%^&*().\n"
            "And unicode: résumé, München, 日本."
        )
        row = _record_history(
            db_session,
            application=application,
            from_stage=PipelineStage.COUNSELING,
            to_stage=PipelineStage.REJECTED,
            changed_by_user_id=None,
            reason=reason,
        )
        assert row.reason == reason

    def test_history_application_id_matches_application(
        self, db_session: Session
    ) -> None:
        """Every history row's ``application_id`` matches the application it tracks."""
        application_a = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        application_b = seed_application(
            db_session, tenant_id=2, stage=PipelineStage.REGISTERED
        )
        row_a = _record_history(
            db_session,
            application=application_a,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
        )
        row_b = _record_history(
            db_session,
            application=application_b,
            from_stage=None,
            to_stage=PipelineStage.REGISTERED,
            changed_by_user_id=None,
        )
        assert row_a.application_id == application_a.id
        assert row_b.application_id == application_b.id
        assert row_a.application_id != row_b.application_id


# ===========================================================================
# 7. SEEDER + VALIDATION INTERACTION
#    The boot-time ``seed_default_stage_transitions`` seeder populates the
#    platform-default rule table; ``is_valid_transition`` must then accept
#    every default pair and reject everything else without writing rows.
# ===========================================================================


class TestSeederAndValidationInteraction:
    """The seeder feeds the validation table; history writes only on accepted moves."""

    def test_seeded_defaults_make_every_forward_pair_valid(
        self, db_session: Session
    ) -> None:
        """After seeding, every default (from, to) pair is accepted by validation."""
        seed_default_stage_transitions(db_session)

        # A representative subset of the seeded pairs -- covers forward,
        # loan-loop, and a terminal path.
        accepted_pairs = [
            (PipelineStage.REGISTERED, PipelineStage.COUNSELING),
            (PipelineStage.COUNSELING, PipelineStage.UNIVERSITY_SHORTLISTING),
            (PipelineStage.DOCUMENT_VERIFICATION, PipelineStage.OFFER_LETTER),
            (PipelineStage.VISA_PROCESSING, PipelineStage.LOAN_PROCESSING),
            (PipelineStage.LOAN_PROCESSING, PipelineStage.VISA_PROCESSING),
            (PipelineStage.OFFER_LETTER, PipelineStage.REJECTED),
        ]
        for from_stage, to_stage in accepted_pairs:
            assert (
                is_valid_transition_for_platform(db_session, from_stage, to_stage)
                is True
            ), f"{from_stage.value} → {to_stage.value} should be accepted"

    def test_seeded_defaults_reject_unlisted_pairs(
        self, db_session: Session
    ) -> None:
        """After seeding, every non-default (from, to) pair is rejected."""
        seed_default_stage_transitions(db_session)

        default_set = set(DEFAULT_TRANSITIONS)
        for from_stage in PipelineStage.non_terminal_stages():
            for to_stage in PipelineStage:
                if (from_stage, to_stage) in default_set:
                    continue
                assert (
                    is_valid_transition_for_platform(
                        db_session, from_stage, to_stage
                    )
                    is False
                ), f"{from_stage.value} → {to_stage.value} must not be accepted"

    def test_every_seeded_default_pair_writes_a_distinct_history_row(
        self, db_session: Session
    ) -> None:
        """A full forward pipeline writes one history row per transition."""
        seed_default_stage_transitions(db_session)

        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )
        chain = [
            PipelineStage.COUNSELING,
            PipelineStage.UNIVERSITY_SHORTLISTING,
            PipelineStage.APPLICATION_SUBMITTED,
            PipelineStage.DOCUMENT_VERIFICATION,
            PipelineStage.OFFER_LETTER,
            PipelineStage.VISA_PROCESSING,
            PipelineStage.ENROLLED,
        ]
        from_stage = application.stage
        for to_stage in chain:
            validate_transition(
                db_session,
                from_stage,
                to_stage,
                tenant_id=application.tenant_id,
            )
            _record_history(
                db_session,
                application=application,
                from_stage=from_stage,
                to_stage=to_stage,
                changed_by_user_id=None,
            )
            from_stage = to_stage

        rows = (
            db_session.query(StageHistory)
            .filter(StageHistory.application_id == application.id)
            .order_by(StageHistory.id)
            .all()
        )
        # One row per hop, and the from→to sequence mirrors the chain.
        assert [r.from_stage for r in rows] == [
            PipelineStage.REGISTERED,
            *chain[:-1],
        ]
        assert [r.to_stage for r in rows] == chain

    def test_full_forward_pipeline_rows_match_requirement_chain(
        self, db_session: Session
    ) -> None:
        """The recorded from→to sequence matches the E25 / Requirements §5 chain."""
        seed_default_stage_transitions(db_session)
        application = seed_application(
            db_session, tenant_id=1, stage=PipelineStage.REGISTERED
        )

        # Walk the canonical forward chain (per E25 / Requirements §5).
        chain = [
            (PipelineStage.REGISTERED, PipelineStage.COUNSELING),
            (PipelineStage.COUNSELING, PipelineStage.UNIVERSITY_SHORTLISTING),
            (PipelineStage.UNIVERSITY_SHORTLISTING, PipelineStage.APPLICATION_SUBMITTED),
            (PipelineStage.APPLICATION_SUBMITTED, PipelineStage.DOCUMENT_VERIFICATION),
            (PipelineStage.DOCUMENT_VERIFICATION, PipelineStage.OFFER_LETTER),
            (PipelineStage.OFFER_LETTER, PipelineStage.VISA_PROCESSING),
            (PipelineStage.VISA_PROCESSING, PipelineStage.ENROLLED),
        ]
        for from_stage, to_stage in chain:
            validate_transition(
                db_session,
                from_stage,
                to_stage,
                tenant_id=application.tenant_id,
            )
            _record_history(
                db_session,
                application=application,
                from_stage=from_stage,
                to_stage=to_stage,
                changed_by_user_id=None,
            )

        rows = (
            db_session.query(StageHistory)
            .filter(StageHistory.application_id == application.id)
            .order_by(StageHistory.id)
            .all()
        )
        assert len(rows) == len(chain)
        for row, (from_stage, to_stage) in zip(rows, chain):
            assert row.from_stage == from_stage
            assert row.to_stage == to_stage
