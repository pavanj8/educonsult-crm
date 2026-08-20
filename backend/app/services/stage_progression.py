"""Stage progression service (E25; Journey J18).

Provides transition validation against the database rule table.
"""

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.stage_transition import StageTransition
from app.pipeline.stages import PipelineStage


class InvalidStageTransitionError(ValueError):
    """Raised when a stage transition is not allowed.

    Attributes:
        from_stage: The stage the application is transitioning from.
        to_stage: The stage the application is attempting to transition to.
    """

    def __init__(self, from_stage: PipelineStage, to_stage: PipelineStage) -> None:
        self.from_stage = from_stage
        self.to_stage = to_stage
        super().__init__(
            f"Transition from '{from_stage.value}' to '{to_stage.value}' is not allowed."
        )


def is_valid_transition(
    db: Session,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
    tenant_id: int,
) -> bool:
    """Return True when the given transition is allowed for the tenant (or platform default).

    Resolution order:
      1. If a tenant-specific rule exists (any ``is_active`` value), it overrides
         the platform default for that tenant:
           - Active tenant rule → True
           - Inactive tenant rule → False (explicitly blocked)
      2. If no tenant-specific rule exists, fall back to the platform default
         (``tenant_id`` IS NULL, ``is_active=True``).

    Args:
        db: Active SQLAlchemy session.
        from_stage: The stage the application is currently in.
        to_stage: The stage the application is being advanced to.
        tenant_id: Tenant scope for the transition. REQUIRED -- every request in
            this multi-tenant SaaS must be tenant-scoped (ADR-0001). The function
            refuses to silently fall back to platform defaults when called
            without a tenant id; pass an explicit ``tenant_id`` (or use
            :func:`is_valid_transition_for_platform` for the rare, tenant-free
            bootstrap/maintenance path).

    Returns:
        True iff the transition is permitted for ``tenant_id``.
    """
    if from_stage.is_terminal:
        return False

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


def is_valid_transition_for_platform(
    db: Session,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
) -> bool:
    """Return True when the platform-default transition rule permits the move.

    This is the tenant-free variant for bootstrap/maintenance contexts (e.g.
    migrations, the application-stage seeder, the optional Test Agent
    fixtures that don't care about tenancy). Production request paths must
    use :func:`is_valid_transition` with an explicit ``tenant_id``.

    Terminal-source transitions are always rejected here too.
    """
    if from_stage.is_terminal:
        return False
    rule = db.query(StageTransition).filter(
        and_(
            StageTransition.from_stage == from_stage,
            StageTransition.to_stage == to_stage,
            StageTransition.tenant_id.is_(None),
            StageTransition.is_active.is_(True),
        )
    ).first()
    return rule is not None


def validate_transition(
    db: Session,
    from_stage: PipelineStage,
    to_stage: PipelineStage,
    tenant_id: int,
) -> None:
    """Raise :class:`InvalidStageTransitionError` if the transition is not allowed."""
    if not is_valid_transition(db, from_stage, to_stage, tenant_id):
        raise InvalidStageTransitionError(from_stage, to_stage)