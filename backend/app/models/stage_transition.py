from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.pipeline.stages import PipelineStage


class StageTransition(Base):
    """Valid stage transition rules table (E25; Journey J18).

    Each row declares that ``from_stage`` may advance to ``to_stage`` within
    a given tenant. Tenants inherit a platform-wide default when no
    tenant-specific override exists (tenant_id IS NULL rows).

    For v1 the default rule set encodes the forward-progression pipeline:
      REGISTERED → COUNSELING → UNIVERSITY_SHORTLISTING → APPLICATION_SUBMITTED →
      DOCUMENT_VERIFICATION → OFFER_LETTER → VISA_PROCESSING → ENROLLED

    LOAN_PROCESSING is entered from VISA_PROCESSING when a student opts in (E36),
    and transitions back to VISA_PROCESSING once the loan is resolved.

    Terminal stages (ENROLLED, REJECTED, WITHDRAWN) have no outgoing transitions.

    Design note (ADR-0001 / v1 multi-tenant scope): this is intentionally a
    single table with NULL-as-default rather than a separate "global rules"
    table joined to per-tenant overrides. The unique constraint is
    ``(from_stage, to_stage, tenant_id)`` so each tenant can have at most one
    active row per (from, to) pair, and the NULL row is the shared default.
    """

    __tablename__ = "stage_transitions"
    __table_args__ = (
        UniqueConstraint("from_stage", "to_stage", "tenant_id", name="uq_stage_transition"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_stage: Mapped[PipelineStage] = mapped_column(
        Enum(
            PipelineStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    to_stage: Mapped[PipelineStage] = mapped_column(
        Enum(
            PipelineStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    # NULL tenant_id means "platform default" applicable to all tenants.
    # A tenant-specific row overrides the default for that tenant.
    tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )