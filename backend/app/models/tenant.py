from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Tenant(Base):
    """Consultancy tenant record (E8 tenant management; ADR-0001 root entity).

    Tenant profile / branding columns (E10; Journey J3; Requirements §1
    White-labeling + Currency) live on this same row to keep the tenant
    root entity self-contained:

    * ``logo_url`` -- URL of the uploaded tenant logo (E10 task #111 owns the
      upload endpoint). Nullable because the platform seeds tenants before
      any logo is provided.
    * ``brand_color`` -- primary brand color used by the frontend shell to
      theme the app (E10 task #113). Stored as a 7-char ``#RRGGBB`` string.
      Nullable for tenants that have not picked one yet.
    * ``currency`` -- ISO 4217 display/reporting currency code (no live FX
      conversion per Requirements §1 Currency). Defaults to ``"INR"``
      because the home market is India; the helper in :mod:`app.i18n.currency`
      validates the shape when callers (the future PATCH endpoint, task #110)
      need to write to it.
    * ``plan_id`` -- nullable FK to ``plans.id`` set by the E9 task #106
      super-admin assign/change-plan API. Nullable so a brand-new tenant
      exists with no assigned plan until the Super Admin explicitly picks
      one; the J38 owner plan-usage view treats ``NULL`` as "no plan yet,
      please contact the platform".
    """

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    brand_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="INR"
    )
<<<<<<< HEAD
    # E9 task #107: nullable FK to the platform-level plans catalog
    # (E9 task #105). E9 task #106 (assign/change plan API) owns the
    # write side; this module only consumes the column to enforce
    # per-tier limits (branches / staff / students). Nullable because
    # a tenant exists before a Super Admin has picked a tier, and
    # ``PlanLimitExceeded`` enforcement short-circuits to no-cap when
    # ``plan_id`` is NULL -- so existing tenants created before a
    # plan was assigned continue to create branches / staff /
    # students without errors. ON DELETE RESTRICT matches the
    # catalog row's lifecycle (active tiers cannot be removed while
    # tenants still reference them).
=======
    # E9 task #106: nullable FK to the platform-level plans catalog
    # (E9 task #105). A tenant exists before any plan is chosen; the
    # super-admin assign/change-plan endpoint sets this. ON DELETE is
    # left to the database default (RESTRICT) so an active tier cannot
    # be removed while tenants still reference it.
>>>>>>> origin/main
    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
<<<<<<< HEAD
=======
    # SQLAlchemy relationship used by the ``TenantResponse.plan`` nested
    # field (E9 task #106). The endpoint typically re-fetches the plan
    # after the FK change commits; this relationship is for the
    # ``from_attributes=True`` Pydantic response shape on the GET
    # endpoints.
>>>>>>> origin/main
    plan = relationship("Plan", foreign_keys=[plan_id])
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
