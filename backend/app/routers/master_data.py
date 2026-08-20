"""Public tenant-scoped master-data list routes (E14/E16; Journey J7/J9)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.country import Country
from app.models.program import Program
from app.models.tenant import Tenant
from app.models.university import University
from app.schemas.master_data import CountryResponse, ProgramResponse, UniversityResponse

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Master data service is temporarily unavailable"


def _get_tenant_by_slug(db: Session, slug: str) -> Tenant:
    try:
        tenant = (
            db.query(Tenant)
            .filter(func.lower(Tenant.slug) == slug.strip().lower())
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return tenant


@router.get("/{slug}/countries", response_model=list[CountryResponse])
def list_countries(
    slug: str,
    db: Session = Depends(get_db),
) -> list[Country]:
    """Public list of admin-managed countries for a consultancy (no auth)."""
    tenant = _get_tenant_by_slug(db, slug)
    try:
        return (
            db.query(Country)
            .filter(Country.tenant_id == tenant.id)
            .order_by(Country.name)
            .all()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/{slug}/universities", response_model=list[UniversityResponse])
def list_universities(
    slug: str,
    country_id: Annotated[int, Query(ge=1)],
    db: Session = Depends(get_db),
) -> list[University]:
    """Public list of universities for a country within a consultancy (no auth)."""
    tenant = _get_tenant_by_slug(db, slug)
    try:
        country = (
            db.query(Country)
            .filter(Country.id == country_id, Country.tenant_id == tenant.id)
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if country is None:
        return []

    try:
        return (
            db.query(University)
            .filter(
                University.tenant_id == tenant.id,
                University.country_id == country_id,
            )
            .order_by(University.name)
            .all()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/{slug}/programs", response_model=list[ProgramResponse])
def list_programs(
    slug: str,
    university_id: Annotated[int, Query(ge=1)],
    db: Session = Depends(get_db),
) -> list[Program]:
    """Public list of programs for a university within a consultancy (no auth)."""
    tenant = _get_tenant_by_slug(db, slug)
    try:
        university = (
            db.query(University)
            .filter(University.id == university_id, University.tenant_id == tenant.id)
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if university is None:
        return []

    try:
        return (
            db.query(Program)
            .filter(
                Program.tenant_id == tenant.id,
                Program.university_id == university_id,
            )
            .order_by(Program.name)
            .all()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None
