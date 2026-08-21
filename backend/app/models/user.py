from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.rbac.roles import Role


class User(Base):
    """Platform user account (E5 auth; ADR-0001 tenant_id, ADR-0004 role scoping).

    Student self-registration profile fields (E16; Requirements §5) are stored on
    ``User`` rows with ``role=STUDENT``. Structured target country/university/program
    IDs reference master data tables added in E14.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Per-tenant email uniqueness is enforced at the database layer by a
    # composite UNIQUE(tenant_id, email) constraint added in migration
    # ``i2j3k4l5m6n7`` (E16 issue #140; docs/requirements.md §1 — every table
    # carries ``tenant_id``). The non-unique index remains so the global
    # case-insensitive login lookup in ``backend/app/routers/auth.py`` can
    # still use it.
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=50, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_country_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    target_university_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    target_program_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
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
