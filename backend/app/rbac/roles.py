from enum import StrEnum


class Role(StrEnum):
    """Platform and tenant roles (Requirements §3, ADR-0004)."""

    SUPER_ADMIN = "super_admin"
    CONSULTANCY_OWNER = "consultancy_owner"
    BRANCH_MANAGER = "branch_manager"
    COUNSELOR = "counselor"
    DOCUMENT_VERIFIER = "document_verifier"
    VISA_PROCESSOR = "visa_processor"
    RECEPTIONIST = "receptionist"
    STUDENT = "student"
