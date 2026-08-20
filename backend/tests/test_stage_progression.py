"""Tests for Stage enum and stage transition rule table (E25; Journey J18)."""

import pytest
from sqlalchemy.orm import Session

from app.models.stage_transition import StageTransition
from app.pipeline.default_transitions import (
    DEFAULT_TRANSITIONS,
    seed_default_stage_transitions,
)
from app.pipeline.stages import PipelineStage
from app.services.stage_progression import (
    InvalidStageTransitionError,
    is_valid_transition,
    is_valid_transition_for_platform,
    validate_transition,
)
from tests.factories.timestamps import utc_now


class TestStageEnum:
    """Tests for the PipelineStage StrEnum."""

    def test_all_stages_have_string_values(self) -> None:
        """Every stage value is a non-empty lowercase string."""
        for stage in PipelineStage:
            assert isinstance(stage.value, str)
            assert stage.value == stage.value.lower()
            assert len(stage.value) > 0

    def test_terminal_stages(self) -> None:
        """Terminal stages are enrolled, rejected, and withdrawn."""
        terminal = PipelineStage.terminal_stages()
        assert PipelineStage.ENROLLED in terminal
        assert PipelineStage.REJECTED in terminal
        assert PipelineStage.WITHDRAWN in terminal
        assert len(terminal) == 3

    def test_non_terminal_stages(self) -> None:
        """Non-terminal stages are all stages except the three terminals."""
        non_terminal = PipelineStage.non_terminal_stages()
        assert PipelineStage.REGISTERED in non_terminal
        assert PipelineStage.COUNSELING in non_terminal
        assert PipelineStage.UNIVERSITY_SHORTLISTING in non_terminal
        assert PipelineStage.APPLICATION_SUBMITTED in non_terminal
        assert PipelineStage.DOCUMENT_VERIFICATION in non_terminal
        assert PipelineStage.OFFER_LETTER in non_terminal
        assert PipelineStage.VISA_PROCESSING in non_terminal
        assert PipelineStage.LOAN_PROCESSING in non_terminal
        # Terminal stages must NOT be in non-terminal
        assert PipelineStage.ENROLLED not in non_terminal
        assert PipelineStage.REJECTED not in non_terminal
        assert PipelineStage.WITHDRAWN not in non_terminal

    def test_is_terminal_property(self) -> None:
        """is_terminal returns True only for terminal stages."""
        assert PipelineStage.ENROLLED.is_terminal is True
        assert PipelineStage.REJECTED.is_terminal is True
        assert PipelineStage.WITHDRAWN.is_terminal is True
        assert PipelineStage.REGISTERED.is_terminal is False
        assert PipelineStage.COUNSELING.is_terminal is False
        assert PipelineStage.VISA_PROCESSING.is_terminal is False

    def test_stage_count(self) -> None:
        """There are exactly 11 stages as per Requirements §5."""
        assert len(PipelineStage) == 11


class TestStageTransitionModel:
    """Tests for the StageTransition ORM model."""

    def test_create_transition_record(
        self,
        db_session: Session,
    ) -> None:
        """StageTransition row can be created with from/to stages and null tenant."""
        now = utc_now()
        transition = StageTransition(
            from_stage=PipelineStage.REGISTERED,
            to_stage=PipelineStage.COUNSELING,
            tenant_id=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(transition)
        db_session.commit()
        db_session.refresh(transition)

        assert transition.id is not None
        assert transition.from_stage == PipelineStage.REGISTERED
        assert transition.to_stage == PipelineStage.COUNSELING
        assert transition.tenant_id is None
        assert transition.is_active is True

    def test_create_tenant_specific_override(
        self,
        db_session: Session,
    ) -> None:
        """Tenant-specific rows can be created with a tenant_id and are inactive by default."""
        now = utc_now()
        transition = StageTransition(
            from_stage=PipelineStage.REGISTERED,
            to_stage=PipelineStage.COUNSELING,
            tenant_id=42,
            is_active=False,
            created_at=now,
            updated_at=now,
        )
        db_session.add(transition)
        db_session.commit()
        db_session.refresh(transition)

        assert transition.id is not None
        assert transition.from_stage == PipelineStage.REGISTERED
        assert transition.to_stage == PipelineStage.COUNSELING
        assert transition.tenant_id == 42
        assert transition.is_active is False


class TestDefaultTransitionsContent:
    """Tests for the DEFAULT_TRANSITIONS constant (the platform rule set).

    These tests derive the expected rule set from the requirements
    (Requirements §5; E25/E36/E37/E38/E39/E40) rather than mirroring the
    implementation -- so any rule dropped from the constant is caught
    loudly here.
    """

    def test_default_transitions_covers_all_forward_progression(self) -> None:
        """The forward progression REGISTERED → ... → VISA_PROCESSING → ENROLLED is seeded."""
        expected_forward = {
            (PipelineStage.REGISTERED, PipelineStage.COUNSELING),
            (PipelineStage.COUNSELING, PipelineStage.UNIVERSITY_SHORTLISTING),
            (PipelineStage.UNIVERSITY_SHORTLISTING, PipelineStage.APPLICATION_SUBMITTED),
            (PipelineStage.APPLICATION_SUBMITTED, PipelineStage.DOCUMENT_VERIFICATION),
            (PipelineStage.DOCUMENT_VERIFICATION, PipelineStage.OFFER_LETTER),
            (PipelineStage.OFFER_LETTER, PipelineStage.VISA_PROCESSING),
            (PipelineStage.VISA_PROCESSING, PipelineStage.ENROLLED),
        }
        assert expected_forward.issubset(set(DEFAULT_TRANSITIONS))

    def test_default_transitions_includes_loan_loop(self) -> None:
        """VISA_PROCESSING ↔ LOAN_PROCESSING loop is seeded (Req §5 Loan Processing)."""
        loan_pairs = {
            (PipelineStage.VISA_PROCESSING, PipelineStage.LOAN_PROCESSING),
            (PipelineStage.LOAN_PROCESSING, PipelineStage.VISA_PROCESSING),
        }
        assert loan_pairs.issubset(set(DEFAULT_TRANSITIONS))

    def test_default_transitions_includes_all_terminal_rejections(self) -> None:
        """Every non-terminal stage can transition to REJECTED and WITHDRAWN.

        Required by E39 (Mark Rejected) and E40 (Mark Withdrawn); 8 non-terminal
        stages × 2 terminal targets = 16 rows.
        """
        non_terminal = PipelineStage.non_terminal_stages()
        expected_terminal = set()
        for from_stage in non_terminal:
            expected_terminal.add((from_stage, PipelineStage.REJECTED))
            expected_terminal.add((from_stage, PipelineStage.WITHDRAWN))
        assert expected_terminal.issubset(set(DEFAULT_TRANSITIONS))

    def test_default_transitions_excludes_terminal_sources(self) -> None:
        """No transition originates from a terminal stage (terminals are absorbing)."""
        terminal = PipelineStage.terminal_stages()
        for terminal_stage in terminal:
            for to_stage in PipelineStage:
                assert (terminal_stage, to_stage) not in set(DEFAULT_TRANSITIONS)


class TestIsValidTransition:
    """Tests for the is_valid_transition() service function."""

    def test_forward_progression_is_valid(self, db_session: Session) -> None:
        """Normal forward progression stages are valid transitions."""
        _seed_default_transition(db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING)
        assert (
            is_valid_transition(db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING, tenant_id=1)
            is True
        )

    def test_visa_to_enrolled_is_valid(self, db_session: Session) -> None:
        """VISA_PROCESSING → ENROLLED is a valid terminal progression."""
        _seed_default_transition(db_session, PipelineStage.VISA_PROCESSING, PipelineStage.ENROLLED)
        assert (
            is_valid_transition(
                db_session, PipelineStage.VISA_PROCESSING, PipelineStage.ENROLLED, tenant_id=1
            )
            is True
        )

    def test_invalid_forward_jump_rejected(self, db_session: Session) -> None:
        """Jumping ahead multiple stages (e.g. REGISTERED → DOCUMENT_VERIFICATION) is invalid."""
        _seed_default_transition(db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING)
        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.DOCUMENT_VERIFICATION, tenant_id=1
            )
            is False
        )

    def test_backward_transition_rejected(self, db_session: Session) -> None:
        """Backward transitions (e.g. COUNSELING → REGISTERED) are invalid."""
        _seed_default_transition(db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING)
        assert (
            is_valid_transition(
                db_session, PipelineStage.COUNSELING, PipelineStage.REGISTERED, tenant_id=1
            )
            is False
        )

    def test_transition_from_terminal_rejected(self, db_session: Session) -> None:
        """No transition is allowed FROM a terminal stage."""
        assert (
            is_valid_transition(
                db_session, PipelineStage.ENROLLED, PipelineStage.REGISTERED, tenant_id=1
            )
            is False
        )
        assert (
            is_valid_transition(
                db_session, PipelineStage.REJECTED, PipelineStage.REGISTERED, tenant_id=1
            )
            is False
        )
        assert (
            is_valid_transition(
                db_session, PipelineStage.WITHDRAWN, PipelineStage.REGISTERED, tenant_id=1
            )
            is False
        )

    def test_undefined_transition_rejected(self, db_session: Session) -> None:
        """Transitions not in the rule table are rejected."""
        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.ENROLLED, tenant_id=1
            )
            is False
        )

    def test_loan_processing_cycle(self, db_session: Session) -> None:
        """LOAN_PROCESSING ↔ VISA_PROCESSING forms a valid two-way transition."""
        _seed_default_transition(
            db_session, PipelineStage.VISA_PROCESSING, PipelineStage.LOAN_PROCESSING
        )
        _seed_default_transition(
            db_session, PipelineStage.LOAN_PROCESSING, PipelineStage.VISA_PROCESSING
        )
        assert (
            is_valid_transition(
                db_session, PipelineStage.VISA_PROCESSING, PipelineStage.LOAN_PROCESSING, tenant_id=1
            )
            is True
        )
        assert (
            is_valid_transition(
                db_session, PipelineStage.LOAN_PROCESSING, PipelineStage.VISA_PROCESSING, tenant_id=1
            )
            is True
        )

    def test_terminal_from_visa_processing(self, db_session: Session) -> None:
        """VISA_PROCESSING can transition to REJECTED or WITHDRAWN."""
        _seed_default_transition(db_session, PipelineStage.VISA_PROCESSING, PipelineStage.REJECTED)
        _seed_default_transition(db_session, PipelineStage.VISA_PROCESSING, PipelineStage.WITHDRAWN)
        assert (
            is_valid_transition(
                db_session, PipelineStage.VISA_PROCESSING, PipelineStage.REJECTED, tenant_id=1
            )
            is True
        )
        assert (
            is_valid_transition(
                db_session, PipelineStage.VISA_PROCESSING, PipelineStage.WITHDRAWN, tenant_id=1
            )
            is True
        )

    def test_tenant_specific_override_blocks_default(self, db_session: Session) -> None:
        """An inactive tenant-specific rule blocks the platform default for that tenant."""
        # Seed platform default: registered → counseling = ALLOWED
        _seed_default_transition(db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING)
        # Seed tenant-1 override: registered → counseling = DISALLOWED
        _seed_tenant_transition(
            db_session, 1, PipelineStage.REGISTERED, PipelineStage.COUNSELING, is_active=False
        )

        # With tenant_id=1, the inactive override takes effect (transition is NOT valid)
        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING, tenant_id=1
            )
            is False
        )

    def test_tenant_active_override_allows(self, db_session: Session) -> None:
        """An active tenant-specific rule takes precedence over any default."""
        # Do NOT seed a platform default for this transition
        # Seed tenant-1 override: registered → counseling = ALLOWED
        _seed_tenant_transition(
            db_session, 1, PipelineStage.REGISTERED, PipelineStage.COUNSELING, is_active=True
        )

        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING, tenant_id=1
            )
            is True
        )

    def test_tenant_falls_back_to_platform_default(self, db_session: Session) -> None:
        """When no tenant-specific rule exists, platform default is used."""
        _seed_default_transition(db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING)
        # No tenant-specific rule for tenant 2
        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING, tenant_id=2
            )
            is True
        )

    def test_inactive_tenant_rule_without_default_rejected(self, db_session: Session) -> None:
        """An inactive tenant-specific rule with no default means the transition is blocked."""
        # No platform default for this transition
        # Seed tenant-1 inactive rule: registered → enrolled = blocked
        _seed_tenant_transition(
            db_session, 1, PipelineStage.REGISTERED, PipelineStage.ENROLLED, is_active=False
        )

        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.ENROLLED, tenant_id=1
            )
            is False
        )

    def test_inactive_platform_default_is_ignored(self, db_session: Session) -> None:
        """An is_active=False platform default must NOT permit a transition for any tenant.

        Only ACTIVE platform defaults are consulted as the fallback after a
        tenant-specific rule. This covers the previously-flagged coverage gap
        for "platform default exists but is deactivated".
        """
        # Seed inactive platform default: registered → counseling = blocked
        _seed_default_transition(
            db_session,
            PipelineStage.REGISTERED,
            PipelineStage.COUNSELING,
            is_active=False,
        )
        # Tenant 7 has NO override row; only the deactivated default applies.
        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING, tenant_id=7
            )
            is False
        )

    def test_tenant_isolation_tenant_1_does_not_see_tenant_2_rules(self, db_session: Session) -> None:
        """Tenant 1's active rules must not leak into tenant 2's transition checks.

        This test proves tenant isolation: conflicting is_active values for different
        tenants must not affect each other's transition validation.
        """
        # Tenant 1 has registered → counseling ALLOWED
        _seed_tenant_transition(
            db_session, 1, PipelineStage.REGISTERED, PipelineStage.COUNSELING, is_active=True
        )
        # Tenant 2 has registered → counseling DISALLOWED
        _seed_tenant_transition(
            db_session, 2, PipelineStage.REGISTERED, PipelineStage.COUNSELING, is_active=False
        )

        # Tenant 1 sees ALLOWED
        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING, tenant_id=1
            )
            is True
        )
        # Tenant 2 sees DISALLOWED
        assert (
            is_valid_transition(
                db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING, tenant_id=2
            )
            is False
        )


class TestValidateTransition:
    """Tests for the validate_transition() service function."""

    def test_valid_transition_raises_nothing(self, db_session: Session) -> None:
        """validate_transition() does not raise when transition is valid."""
        _seed_default_transition(db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING)
        # Should not raise
        validate_transition(db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING, tenant_id=1)

    def test_invalid_transition_raises(self, db_session: Session) -> None:
        """validate_transition() raises InvalidStageTransitionError on invalid transition."""
        with pytest.raises(InvalidStageTransitionError) as exc_info:
            validate_transition(
                db_session,
                PipelineStage.REGISTERED,
                PipelineStage.DOCUMENT_VERIFICATION,
                tenant_id=1,
            )
        assert exc_info.value.from_stage == PipelineStage.REGISTERED
        assert exc_info.value.to_stage == PipelineStage.DOCUMENT_VERIFICATION
        assert "not allowed" in str(exc_info.value)

    def test_terminal_stage_raises(self, db_session: Session) -> None:
        """validate_transition() raises when trying to transition from a terminal stage."""
        with pytest.raises(InvalidStageTransitionError) as exc_info:
            validate_transition(
                db_session, PipelineStage.ENROLLED, PipelineStage.REGISTERED, tenant_id=1
            )
        assert exc_info.value.from_stage == PipelineStage.ENROLLED


class TestSeedDefaultStageTransitions:
    """Tests for the runtime seeder that populates the rule table on app boot."""

    def test_seed_inserts_all_default_rows_into_empty_table(self, db_session: Session) -> None:
        """Calling the seeder on an empty table inserts every DEFAULT_TRANSITIONS row."""
        inserted = seed_default_stage_transitions(db_session)
        assert inserted == len(DEFAULT_TRANSITIONS)

        rows = {
            (row.from_stage, row.to_stage)
            for row in db_session.query(StageTransition)
            .filter(StageTransition.tenant_id.is_(None))
            .all()
        }
        expected = set(DEFAULT_TRANSITIONS)
        assert rows == expected
        # All default rows must be active.
        for row in db_session.query(StageTransition).filter(
            StageTransition.tenant_id.is_(None)
        ).all():
            assert row.is_active is True

    def test_seed_is_idempotent(self, db_session: Session) -> None:
        """Running the seeder a second time inserts zero new rows."""
        first = seed_default_stage_transitions(db_session)
        second = seed_default_stage_transitions(db_session)
        third = seed_default_stage_transitions(db_session)
        assert first == len(DEFAULT_TRANSITIONS)
        assert second == 0
        assert third == 0

    def test_seed_preserves_tenant_overrides(self, db_session: Session) -> None:
        """Pre-existing tenant-specific rows must not be touched by the seeder."""
        # Pre-seed a tenant-specific inactive override that conflicts with the default.
        _seed_tenant_transition(
            db_session, 5, PipelineStage.REGISTERED, PipelineStage.COUNSELING, is_active=False
        )
        before_count = db_session.query(StageTransition).filter(
            StageTransition.tenant_id == 5
        ).count()

        seed_default_stage_transitions(db_session)

        after_count = db_session.query(StageTransition).filter(
            StageTransition.tenant_id == 5
        ).count()
        assert before_count == 1
        assert after_count == 1
        # The tenant override must remain INACTIVE after seeding.
        row = (
            db_session.query(StageTransition)
            .filter(
                StageTransition.tenant_id == 5,
                StageTransition.from_stage == PipelineStage.REGISTERED,
                StageTransition.to_stage == PipelineStage.COUNSELING,
            )
            .first()
        )
        assert row is not None
        assert row.is_active is False

    def test_is_valid_transition_for_platform_helper(self, db_session: Session) -> None:
        """The tenant-free helper returns True for a seeded default and False otherwise."""
        seed_default_stage_transitions(db_session)
        assert (
            is_valid_transition_for_platform(
                db_session, PipelineStage.REGISTERED, PipelineStage.COUNSELING
            )
            is True
        )
        assert (
            is_valid_transition_for_platform(
                db_session, PipelineStage.REGISTERED, PipelineStage.ENROLLED
            )
            is False
        )
        # Terminal source still rejected.
        assert (
            is_valid_transition_for_platform(
                db_session, PipelineStage.ENROLLED, PipelineStage.REGISTERED
            )
            is False
        )


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _seed_default_transition(
    db: Session,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
    is_active: bool = True,
) -> StageTransition:
    """Create and commit a platform-default (tenant_id=NULL) transition."""
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


def _seed_tenant_transition(
    db: Session,
    tenant_id: int,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
    is_active: bool = True,
) -> StageTransition:
    """Create and commit a tenant-specific transition."""
    now = utc_now()
    row = StageTransition(
        from_stage=from_stage,
        to_stage=to_stage,
        tenant_id=tenant_id,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row