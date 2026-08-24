"""Subscription plan catalog for the platform billing tiers (E9; Journey J2).

* ``PlanTier`` -- the three canonical subscription tiers from
  Requirements §4: ``STARTER``, ``GROWTH``, ``ENTERPRISE``.
* ``Plan`` -- one row per tier; holds the per-tier limits consumed by
  the E9 task #107 usage limit enforcement checks (``max_branches``,
  ``max_staff``, ``max_students``) and the J38 owner plan-usage view
  (E45).

Why this is a platform-level catalog (NOT tenant-scoped):

* Requirements §4 -- the three tier *names* are a platform constant.
  A tenant picks one of them; they cannot invent their own tier.
* J2 / J38 / J39 / J40 all read plans across tenants, so a single
  global table is the natural shape. The future ``tenants.plan_id``
  FK (E9 task #106 assigns a plan to a tenant; #107 enforces
  limits) is the per-tenant pointer; the row counts against the
  chosen plan's limits.

Limit semantics (``NULL`` means "unlimited"):

* Requirements §4 spells out the three tiers:
  - Starter: ``1 branch, limited staff/students``
  - Growth:  ``multiple branches, higher limits``
  - Enterprise: ``unlimited/custom``
* Concretely the limits columns are nullable so Enterprise can
  advertise ``NULL`` (unlimited) without picking a magic
  ``2**31 - 1`` sentinel. Enforcement (#107) treats ``NULL`` as
  "no cap".

The model lives on ``Base`` (NOT ``TenantScopedBase``) for the
same reason -- one catalog row per tier, no ``tenant_id``.
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlanTier(str, Enum):
    """The three subscription tiers from Requirements §4 Billing.

    Values are stable string codes -- they go on the wire (responses
    for ``GET /tenants/{id}``, the owner plan-usage page, the
    Razorpay checkout) and into the database, so renaming them is a
    migration.
    """

    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class Plan(Base):
    """Platform-level subscription plan row (E9; Journey J2).

    One row per tier in the canonical catalog. Seeded by the platform
    (the future seed/admin path in E9 task #106 / #108); user code
    reads these rows to render plan pickers and to enforce per-tier
    limits.

    Columns:

    * ``id`` -- surrogate primary key.
    * ``code`` -- stable string tier code (``PlanTier.value``).
      Unique so duplicate catalog rows cannot slip in via seed
      reruns. The ``UniqueConstraint`` creates the backing index,
      which is what ``tenants.plan_id`` lookups and the future
      ``Plan`` API in #106 will key off -- no separate non-unique
      index is added on top of it.
    * ``name`` -- human-readable display name ("Starter", "Growth",
      "Enterprise"). 255 chars covers any future copy tweak.
    * ``description`` -- optional free-text blurb shown on the owner
      plan-usage page (J38) and the Razorpay checkout (J39).
    * ``max_branches`` / ``max_staff`` / ``max_students`` -- per-tier
      caps consumed by E9 task #107. Nullable so Enterprise can
      advertise "unlimited" (Requirements §4) without a magic
      sentinel; enforcement treats NULL as "no cap".
    * ``is_active`` -- whether the tier is currently sellable.
      Retired tiers stay in the table so historical ``tenants.plan_id``
      rows remain readable; the active-tier picker filters on this.
    * ``created_at`` / ``updated_at`` -- standard audit timestamps,
      matching the convention used on every other model in the repo.
    """

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(
        SAEnum(
            PlanTier,
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Limits -- NULL means "unlimited" (Enterprise per Requirements §4).
    max_branches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_staff: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_students: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
