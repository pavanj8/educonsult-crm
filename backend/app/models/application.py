"""Application model (E18; E21; E36; E37; Requirements §5).

The E21 queue fields are nullable for backwards compatibility with rows
created by E18, which pre-dates the branch and counselor-assignment
columns. Follow-ups tracked for the tightening of these columns to NOT NULL:

- **E19 — Counselor Auto-Assignment** (Journey J12): populates
  ``assigned_counselor_id`` automatically on new applications.
- **E20 — Manual Counselor Reassignment** (Journey J13): allows manual
  updates of ``assigned_counselor_id`` (and ``branch_id``) via the staff
  reassignment API.
- **E21 — Counselor Dashboard & Queue** (this issue; Journey J14): the
  ``GET /applications/assigned-to-me`` endpoint reads
  ``branch_id`` / ``assigned_counselor_id`` for the role-scoped queue.
- **E36 — Student Loan Opt-in** (Journey J29): ``loan_opt_in`` tracks
  whether the student opted into loan tracking on the application
  (Requirements §5: "Loans: Tracking-only fields (opted-in, status,
  amount, lender) — no separate loan officer workflow for v1").
  Default ``False`` for backwards compatibility with rows created
  before E36.
- **E37 — Staff Loan Status Update** (Journey J30): ``loan_status``,
  ``loan_lender``, and ``loan_amount`` track the loan-tracking
  fields staff record via the update-loan-status API (Requirements §5:
  "Loans: Tracking-only fields (opted-in, status, amount, lender) —
  no separate loan officer workflow for v1"). All three are nullable
  so a staff member can record the status / lender ahead of the
  amount, or clear a previously-recorded value.

Until those follow-ups land, an ``Application`` may be persisted with
``branch_id IS NULL`` and/or ``assigned_counselor_id IS NULL``. The
constraints can be tightened in the respective follow-up issues when the
columns are reliably populated for new rows.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedBase
from app.pipeline.stages import PipelineStage as ApplicationStage

__all__ = ["Application", "ApplicationStage"]


class Application(TenantScopedBase):
    """Student application to a university/program (E18; E21; E36; E37)."""

    __tablename__ = "applications"

    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_counselor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    university_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ApplicationStage.REGISTERED,
    )
    loan_opt_in: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    # E37 task #200: tracking-only loan fields (Journey J30; Requirements
    # §5 "Loans: Tracking-only fields (opted-in, status, amount,
    # lender) — no separate loan officer workflow for v1"). All nullable
    # so staff can record them progressively: status first, lender next,
    # amount last (or clear a previously-recorded value via explicit
    # null in the PATCH body). ``loan_amount`` is ``Numeric(12, 2)`` to
    # match the precision used for tenant financial fields elsewhere on
    # the platform; the Pydantic schema on the update API is the
    # contract.
    loan_status: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
    )
    loan_lender: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True,
    )
    loan_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=12, scale=2), nullable=True,
    )
