"""Validate structured study-preference ids against tenant master data (E16/E14)."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.country import Country
from app.models.program import Program
from app.models.university import University
from app.schemas.student import RegisterStudentRequest


def validate_target_master_data(
    db: Session,
    tenant_id: int,
    payload: RegisterStudentRequest,
) -> None:
    """Reject unknown or inconsistent target country/university/program ids."""
    country: Country | None = None
    university: University | None = None
    program: Program | None = None

    if payload.target_country_id is not None:
        country = (
            db.query(Country)
            .filter(
                Country.id == payload.target_country_id,
                Country.tenant_id == tenant_id,
            )
            .one_or_none()
        )
        if country is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid target country",
            )

    if payload.target_university_id is not None:
        university = (
            db.query(University)
            .filter(
                University.id == payload.target_university_id,
                University.tenant_id == tenant_id,
            )
            .one_or_none()
        )
        if university is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid target university",
            )
        if country is not None and university.country_id != country.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Target university does not belong to the selected country",
            )

    if payload.target_program_id is not None:
        program = (
            db.query(Program)
            .filter(
                Program.id == payload.target_program_id,
                Program.tenant_id == tenant_id,
            )
            .one_or_none()
        )
        if program is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid target program",
            )
        if university is not None and program.university_id != university.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Target program does not belong to the selected university",
            )
