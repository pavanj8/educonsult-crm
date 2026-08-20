"""Tests for Stage enum and stage transition rule table (E25; Journey J18)."""

import pytest
from sqlalchemy.orm import Session

from app.models.stage_transition import StageTransition
from app.pipeline.stages import Stage
from app.services.stage_progression import (
    InvalidStageTransitionError,
    is_valid_transition,
    validate_transition,
)
from tests.factories.timestamps import utc_now


class TestStageEnum:
    """Tests for the Stage StrEnum."""

    def test_all_stages_have_string_values(self) -> None:
        """Every stage value is a non-empty lowercase string."""
        for stage in Stage:
            assert isinstance(stage.value, str)
            assert stage.value == stage.value.lower()
            assert len(stage.value) > 0

    def test_terminal_stages(self) -> None:
        """Terminal stages are enrolled, rejected, and withdrawn."""
        terminal = Stage.terminal_stages()
        assert Stage.ENROLLED in terminal
        assert Stage.REJECTED in terminal
        assert Stage.WITHDRAWN in terminal
        assert len(terminal) == 3

    def test_non_terminal_stages(self) -> None:
        """Non-terminal stages are all stages except the three terminals."""
        non_terminal = Stage.non_terminal_stages()
        assert Stage.REGISTERED in non_terminal
        assert Stage.COUNSELING in non_terminal
        assert Stage.UNIVERSITY_SHORTLISTING in non_terminal
        assert Stage.APPLICATION_SUBMITTED in non_terminal
        assert Stage.DOCUMENT_VERIFICATION in non_terminal
        assert Stage.OFFER_LETTER in non_terminal
        assert Stage.VISA_PROCESSING in non_terminal
        assert Stage.LOAN_PROCESSING in non_terminal
        # Terminal stages must NOT be in non-terminal
        assert Stage.ENROLLED not in non_terminal
        assert Stage.REJECTED not in non_terminal
        assert Stage.WITHDRAWN not in non_terminal

    def test_is_terminal_property(self) -> None:
        """is_terminal returns True only for terminal stages."""
        assert Stage.ENROLLED.is_terminal is True
        assert Stage.REJECTED.is_terminal is True
        assert Stage.WITHDRAWN.is_terminal is True
        assert Stage.REGISTERED.is_terminal is False
        assert Stage.COUNSELING.is_terminal is False
        assert Stage.VISA_PROCESSING.is_terminal is False

    def test_stage_count(self) -> None:
        """There are exactly 11 stages as per Requirements §5."""
        assert len(Stage) == 11


class TestStageTransitionModel:
    """Tests for the StageTransition ORM model."""

    def test_create_transition_record(
        self,
        db_session: Session,
    ) -> None:
        """StageTransition row can be created with from/to stages and null tenant."""
        now = utc_now()
        transition = StageTransition(
            from_stage=Stage.REGISTERED,
            to_stage=Stage.COUNSELING,
            tenant_id=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db_session.add(transition)
        db_session.commit()
        db_session.refresh(transition)

        assert transition.id is not None
        assert transition.from_stage == Stage.REGISTERED
        assert transition.to_stage == Stage.COUNSELING
        assert transition.tenant_id is None
        assert transition.is_active is True

    def test_create_tenant_specific_override(
        self,
        db_session: Session,
    ) -> None:
        """Tenant-specific rows can be created with a tenant_id and are inactive by default."""
        now = utc_now()
        transition = StageTransition(
            from_stage=Stage.REGISTERED,
            to_stage=Stage.COUNSELING,
            tenant_id=42,
            is_active=False,
            created_at=now,
            updated_at=now,
        )
        db_session.add(transition)
        db_session.commit()
        db_session.refresh(transition)

        assert transition.id is not None
        assert transition.from_stage == Stage.REGISTERED
        assert transition.to_stage == Stage.COUNSELING
        assert transition.tenant_id == 42
        assert transition.is_active is False


class TestIsValidTransition:
    """Tests for the is_valid_transition() service function."""

    def test_forward_progression_is_valid(self, db_session: Session) -> None:
        """Normal forward progression stages are valid transitions."""
        _seed_default_transition(db_session, Stage.REGISTERED, Stage.COUNSELING)
        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.COUNSELING) is True

    def test_visa_to_enrolled_is_valid(self, db_session: Session) -> None:
        """VISA_PROCESSING → ENROLLED is a valid terminal progression."""
        _seed_default_transition(db_session, Stage.VISA_PROCESSING, Stage.ENROLLED)
        assert is_valid_transition(db_session, Stage.VISA_PROCESSING, Stage.ENROLLED) is True

    def test_invalid_forward_jump_rejected(self, db_session: Session) -> None:
        """Jumping ahead multiple stages (e.g. REGISTERED → DOCUMENT_VERIFICATION) is invalid."""
        _seed_default_transition(db_session, Stage.REGISTERED, Stage.COUNSELING)
        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.DOCUMENT_VERIFICATION) is False

    def test_backward_transition_rejected(self, db_session: Session) -> None:
        """Backward transitions (e.g. COUNSELING → REGISTERED) are invalid."""
        _seed_default_transition(db_session, Stage.REGISTERED, Stage.COUNSELING)
        assert is_valid_transition(db_session, Stage.COUNSELING, Stage.REGISTERED) is False

    def test_transition_from_terminal_rejected(self, db_session: Session) -> None:
        """No transition is allowed FROM a terminal stage."""
        assert is_valid_transition(db_session, Stage.ENROLLED, Stage.REGISTERED) is False
        assert is_valid_transition(db_session, Stage.REJECTED, Stage.REGISTERED) is False
        assert is_valid_transition(db_session, Stage.WITHDRAWN, Stage.REGISTERED) is False

    def test_undefined_transition_rejected(self, db_session: Session) -> None:
        """Transitions not in the rule table are rejected."""
        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.ENROLLED) is False

    def test_loan_processing_cycle(self, db_session: Session) -> None:
        """LOAN_PROCESSING ↔ VISA_PROCESSING forms a valid two-way transition."""
        _seed_default_transition(db_session, Stage.VISA_PROCESSING, Stage.LOAN_PROCESSING)
        _seed_default_transition(db_session, Stage.LOAN_PROCESSING, Stage.VISA_PROCESSING)
        assert is_valid_transition(db_session, Stage.VISA_PROCESSING, Stage.LOAN_PROCESSING) is True
        assert is_valid_transition(db_session, Stage.LOAN_PROCESSING, Stage.VISA_PROCESSING) is True

    def test_terminal_from_visa_processing(self, db_session: Session) -> None:
        """VISA_PROCESSING can transition to REJECTED or WITHDRAWN."""
        _seed_default_transition(db_session, Stage.VISA_PROCESSING, Stage.REJECTED)
        _seed_default_transition(db_session, Stage.VISA_PROCESSING, Stage.WITHDRAWN)
        assert is_valid_transition(db_session, Stage.VISA_PROCESSING, Stage.REJECTED) is True
        assert is_valid_transition(db_session, Stage.VISA_PROCESSING, Stage.WITHDRAWN) is True

    def test_tenant_specific_override_blocks_default(self, db_session: Session) -> None:
        """An inactive tenant-specific rule blocks the platform default for that tenant."""
        # Seed platform default: registered → counseling = ALLOWED
        _seed_default_transition(db_session, Stage.REGISTERED, Stage.COUNSELING)
        # Seed tenant-1 override: registered → counseling = DISALLOWED
        _seed_tenant_transition(db_session, 1, Stage.REGISTERED, Stage.COUNSELING, is_active=False)

        # With tenant_id=1, the inactive override takes effect (transition is NOT valid)
        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.COUNSELING, tenant_id=1) is False

    def test_tenant_active_override_allows(self, db_session: Session) -> None:
        """An active tenant-specific rule takes precedence over any default."""
        # Do NOT seed a platform default for this transition
        # Seed tenant-1 override: registered → counseling = ALLOWED
        _seed_tenant_transition(db_session, 1, Stage.REGISTERED, Stage.COUNSELING, is_active=True)

        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.COUNSELING, tenant_id=1) is True

    def test_tenant_falls_back_to_platform_default(self, db_session: Session) -> None:
        """When no tenant-specific rule exists, platform default is used."""
        _seed_default_transition(db_session, Stage.REGISTERED, Stage.COUNSELING)
        # No tenant-specific rule for tenant 2
        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.COUNSELING, tenant_id=2) is True

    def test_inactive_tenant_rule_without_default_rejected(self, db_session: Session) -> None:
        """An inactive tenant-specific rule with no default means the transition is blocked."""
        # No platform default for this transition
        # Seed tenant-1 inactive rule: registered → enrolled = blocked
        _seed_tenant_transition(db_session, 1, Stage.REGISTERED, Stage.ENROLLED, is_active=False)

        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.ENROLLED, tenant_id=1) is False

    def test_tenant_isolation_tenant_1_does_not_see_tenant_2_rules(self, db_session: Session) -> None:
        """Tenant 1's active rules must not leak into tenant 2's transition checks.

        This test proves tenant isolation: conflicting is_active values for different
        tenants must not affect each other's transition validation.
        """
        # Tenant 1 has registered → counseling ALLOWED
        _seed_tenant_transition(db_session, 1, Stage.REGISTERED, Stage.COUNSELING, is_active=True)
        # Tenant 2 has registered → counseling DISALLOWED
        _seed_tenant_transition(db_session, 2, Stage.REGISTERED, Stage.COUNSELING, is_active=False)

        # Tenant 1 sees ALLOWED
        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.COUNSELING, tenant_id=1) is True
        # Tenant 2 sees DISALLOWED
        assert is_valid_transition(db_session, Stage.REGISTERED, Stage.COUNSELING, tenant_id=2) is False


class TestValidateTransition:
    """Tests for the validate_transition() service function."""

    def test_valid_transition_raises_nothing(self, db_session: Session) -> None:
        """validate_transition() does not raise when transition is valid."""
        _seed_default_transition(db_session, Stage.REGISTERED, Stage.COUNSELING)
        # Should not raise
        validate_transition(db_session, Stage.REGISTERED, Stage.COUNSELING)

    def test_invalid_transition_raises(self, db_session: Session) -> None:
        """validate_transition() raises InvalidStageTransitionError on invalid transition."""
        with pytest.raises(InvalidStageTransitionError) as exc_info:
            validate_transition(db_session, Stage.REGISTERED, Stage.DOCUMENT_VERIFICATION)
        assert exc_info.value.from_stage == Stage.REGISTERED
        assert exc_info.value.to_stage == Stage.DOCUMENT_VERIFICATION
        assert "not allowed" in str(exc_info.value)

    def test_terminal_stage_raises(self, db_session: Session) -> None:
        """validate_transition() raises when trying to transition from a terminal stage."""
        with pytest.raises(InvalidStageTransitionError) as exc_info:
            validate_transition(db_session, Stage.ENROLLED, Stage.REGISTERED)
        assert exc_info.value.from_stage == Stage.ENROLLED


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _seed_default_transition(
    db: Session,
    from_stage: Stage,
    to_stage: Stage,
) -> StageTransition:
    """Create and commit a platform-default (tenant_id=NULL) active transition."""
    now = utc_now()
    row = StageTransition(
        from_stage=from_stage,
        to_stage=to_stage,
        tenant_id=None,
        is_active=True,
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
    from_stage: Stage,
    to_stage: Stage,
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
