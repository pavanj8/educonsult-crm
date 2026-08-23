"""Tests for the staff-created student response schema."""

from datetime import date

from app.schemas.student import StaffCreateStudentResponse


def test_staff_student_response_excludes_authentication_tokens():
    fields = set(StaffCreateStudentResponse.model_fields)
    assert "access_token" not in fields
    assert "refresh_token" not in fields
    assert fields == {
        "id",
        "email",
        "role",
        "tenant_id",
        "branch_id",
        "name",
        "phone",
        "date_of_birth",
        "target_country_id",
        "target_university_id",
        "target_program_id",
        "created_at",
    }
    assert StaffCreateStudentResponse.model_fields["date_of_birth"].annotation == date
