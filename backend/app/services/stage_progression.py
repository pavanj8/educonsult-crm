"""Stage progression service (E25; Journey J18).

Provides transition validation against the database rule table.
"""

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.stage_transition import StageTransition
from app.pipeline.stages import Stage


class InvalidStageTransitionError(ValueError):
    """Raised when a stage transition is not allowed.

    Attributes:
        from_stage: The stage the application is transitioning from.
        to_stage: The stage the application is attempting to transition to.
    """

    def __init__(self, from_stage: Stage, to_stage: Stage) -> None:
        self.from_stage = from_stage
        self.to_stage = to_stage
        super().__init__(
            f"Transition from '{from_stage.value}' to '{to_stage.value}' is not allowed."
        )


def is_valid_transition(
    db: Session,
    from_stage: Stage,
    to_stage: Stage,
    tenant_id: int | None = None,
) -> bool:
    """Return True when the given transition is allowed for the tenant (or platform default).

    Resolution order:
      1. If a tenant-specific rule exists (any is_active value), it overrides the
         platform default for that tenant.
           - Active tenant rule → True
           - Inactive tenant rule → False (explicitly blocked)
      2. If no tenant-specific rule exists, fall back to the platform default
         (tenant_id IS NULL, is_active=True).

    Note:
        When called from within a request context, tenant_id must NOT be None.
        Passing None in that context silently falls back to platform defaults,
        which may grant unintended transition privileges.
    """
    if from_stage.is_terminal:
        return False

    if tenant_id is not None:
        # Check for tenant-specific rule first (overrides platform default).
        tenant_rule = db.query(StageTransition).filter(
            and_(
                StageTransition.from_stage == from_stage,
                StageTransition.to_stage == to_stage,
                StageTransition.tenant_id == tenant_id,
            )
        ).first()
        if tenant_rule is not None:
            return tenant_rule.is_active

    # Fall back to platform default (tenant_id IS NULL).
    default_rule = db.query(StageTransition).filter(
        and_(
            StageTransition.from_stage == from_stage,
            StageTransition.to_stage == to_stage,
            StageTransition.tenant_id.is_(None),
            StageTransition.is_active.is_(True),
        )
    ).first()
    return default_rule is not None


def validate_transition(
    db: Session,
    from_stage: Stage,
    to_stage: Stage,
    tenant_id: int | None = None,
) -> None:
    """Raise InvalidStageTransitionError if the transition is not allowed."""
    if not is_valid_transition(db, from_stage, to_stage, tenant_id):
        raise InvalidStageTransitionError(from_stage, to_stage)
