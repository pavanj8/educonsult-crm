"""Pydantic schemas for application endpoints (E21; Journey J14)."""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ApplicationStageEnum(str, Enum):
    """Per-application pipeline stages (Requirements §5)."""

    REGISTERED = "registered"
    COUNSELING = "counseling"
    UNIVERSITY_SHORTLISTING = "university_shortlisting"
    APPLICATION_SUBMITTED = "application_submitted"
    DOCUMENT_VERIFICATION = "document_verification"
    OFFER_LETTER = "offer_letter"
    VISA_PROCESSING = "visa_processing"
    LOAN_PROCESSING = "loan_processing"
    ENROLLED = "enrolled"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationResponse(BaseModel):
    """Single application record in list/detail responses (E21)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    branch_id: int
    student_id: int
    assigned_counselor_id: int | None
    university: str
    program: str
    stage: ApplicationStageEnum
    rejection_reason: str | None
    withdrawal_reason: str | None
    enrolled_at: date | None
    created_at: datetime
    updated_at: datetime


class AssignedToMeFilters(BaseModel):
    """Optional filters for GET /applications/assigned-to-me (E21).

    All filter fields are optional. When a field is absent, no filtering
    is applied on that dimension.
    """

    stage: ApplicationStageEnum | None = Field(default=None, description="Filter by pipeline stage")
    branch_id: int | None = Field(default=None, ge=1, description="Filter by branch")
    student_id: int | None = Field(default=None, ge=1, description="Filter by student ID")
