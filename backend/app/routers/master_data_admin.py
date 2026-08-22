"""Admin CRUD routes for master data (E14; Journey J7).

Public read-only list endpoints for the same datasets live in
:mod:`app.routers.master_data` (used by the registration and application
dropdowns, no auth, scoped by tenant slug).

The endpoints here are the admin-scoped counterpart: gated by the
``master_data:manage`` permission (granted to consultancy owner +
branch manager in :mod:`app.rbac.permissions`) and tenant-scoped via
the authenticated caller's ``tenant_id``. All writes (create, update,
delete) inherit ``tenant_id`` from the caller; cross-tenant reads
surface as 404 to prevent tenant-id enumeration (ADR-0004).

Traceability
------------
* Requirements §5 (structured admin-managed master list: target country /
  university / program).
* Journey J7 (Owner/Branch Manager manages master data).
* Epic E14 (Master Data Management); this router is the backend CRUD
  half of the epic. The companion read-only public list endpoints
  are :mod:`app.routers.master_data`; the seed catalog is loaded by
  :mod:`app.seed.runner`; the frontend UI is sibling ticket #128.

Errors
------
* 401 -- caller is not authenticated.
* 403 -- caller has no ``tenant_id`` (Super Admin does not manage
  tenants' master data here; the role grant intentionally excludes
  SUPER_ADMIN so platform admins cannot silently mutate a tenant's
  master data; ticket scope = admin within a tenant).
* 404 -- the target row does not exist OR belongs to a different
  tenant.
* 422 -- validation failure (missing/blank required field) or a
  parent FK (``country_id``, ``university_id``) that resolves outside
  the caller's tenant.
* 503 -- the database is temporarily unavailable.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.country import Country
from app.models.program import Program
from app.models.university import University
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.user import AuthenticatedUser
from app.schemas.master_data import (
    CountryCreateRequest,
    CountryResponse,
    CountryUpdateRequest,
    ProgramCreateRequest,
    ProgramResponse,
    ProgramUpdateRequest,
    UniversityCreateRequest,
    UniversityResponse,
    UniversityUpdateRequest,
)

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Master data service is temporarily unavailable"


def _require_tenant_scope(current_user: AuthenticatedUser) -> int:
    """Reject callers without a tenant id; return the tenant id otherwise.

    The ``master_data:manage`` permission is granted to consultancy
    owner + branch manager in :mod:`app.rbac.permissions`; both roles
    always carry a ``tenant_id``. Super Admin is intentionally
    excluded from the grant so platform-wide tenant administration
    does not silently mutate a tenant's master data through this
    endpoint set.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user.tenant_id


def _get_tenant_country(
    country_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> Country:
    """Load a country belonging to the caller's tenant, or raise 404."""
    tenant_id = _require_tenant_scope(current_user)
    try:
        country = db.get(Country, country_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if country is None or country.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found",
        )
    return country


def _get_tenant_university(
    university_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> University:
    """Load a university belonging to the caller's tenant, or raise 404."""
    tenant_id = _require_tenant_scope(current_user)
    try:
        university = db.get(University, university_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if university is None or university.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="University not found",
        )
    return university


def _get_tenant_program(
    program_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> Program:
    """Load a program belonging to the caller's tenant, or raise 404."""
    tenant_id = _require_tenant_scope(current_user)
    try:
        program = db.get(Program, program_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if program is None or program.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    return program


def _resolve_country_for_tenant(
    country_id: int,
    tenant_id: int,
    db: Session,
) -> Country:
    """Resolve a country FK that must belong to the caller's tenant.

    Used by the university CRUD endpoints: a university's
    ``country_id`` must resolve to a country in the same tenant,
    otherwise the endpoint raises 422 (the value is unprocessable
    for this tenant, not "not found").
    """
    try:
        country = db.get(Country, country_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if country is None or country.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid country for the caller's tenant",
        )
    return country


def _resolve_university_for_tenant(
    university_id: int,
    tenant_id: int,
    db: Session,
) -> University:
    """Resolve a university FK that must belong to the caller's tenant.

    Used by the program CRUD endpoints; mirrors
    :func:`_resolve_country_for_tenant` but for the university FK.
    """
    try:
        university = db.get(University, university_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if university is None or university.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid university for the caller's tenant",
        )
    return university


@router.get("/countries", response_model=list[CountryResponse])
def list_admin_countries(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> list[Country]:
    """List countries managed by the caller's tenant (E14; Journey J7)."""
    tenant_id = _require_tenant_scope(current_user)
    try:
        return (
            db.query(Country)
            .filter(Country.tenant_id == tenant_id)
            .order_by(Country.name)
            .all()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.post(
    "/countries",
    response_model=CountryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_country(
    payload: CountryCreateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> Country:
    """Create a country under the caller's tenant (E14; Journey J7)."""
    tenant_id = _require_tenant_scope(current_user)
    country = Country(
        tenant_id=tenant_id,
        name=payload.name,
        code=payload.code,
    )
    db.add(country)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(country)
    return country


@router.patch("/countries/{country_id}", response_model=CountryResponse)
def update_country(
    country_id: int,
    payload: CountryUpdateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> Country:
    """Update a country's ``name`` and/or ``code`` within the caller's tenant."""
    country = _get_tenant_country(country_id, current_user, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )

    for field, value in update_data.items():
        setattr(country, field, value)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(country)
    return country


@router.delete("/countries/{country_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_country(
    country_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> None:
    """Delete a country within the caller's tenant (E14; Journey J7).

    The endpoint does not pre-check FK usage: cascading effects on
    universities/programs are the caller's responsibility (the
    application enforces this via the FK relationship at commit
    time). A successful delete returns ``204 No Content``.
    """
    country = _get_tenant_country(country_id, current_user, db)
    db.delete(country)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/universities", response_model=list[UniversityResponse])
def list_admin_universities(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> list[University]:
    """List universities managed by the caller's tenant."""
    tenant_id = _require_tenant_scope(current_user)
    try:
        return (
            db.query(University)
            .filter(University.tenant_id == tenant_id)
            .order_by(University.name)
            .all()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.post(
    "/universities",
    response_model=UniversityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_university(
    payload: UniversityCreateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> University:
    """Create a university scoped to a country in the caller's tenant."""
    tenant_id = _require_tenant_scope(current_user)
    _resolve_country_for_tenant(payload.country_id, tenant_id, db)

    university = University(
        tenant_id=tenant_id,
        country_id=payload.country_id,
        name=payload.name,
    )
    db.add(university)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(university)
    return university


@router.patch(
    "/universities/{university_id}", response_model=UniversityResponse
)
def update_university(
    university_id: int,
    payload: UniversityUpdateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> University:
    """Update a university's ``name`` and/or ``country_id`` within the caller's tenant."""
    tenant_id = _require_tenant_scope(current_user)
    university = _get_tenant_university(university_id, current_user, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )

    if "country_id" in update_data:
        _resolve_country_for_tenant(update_data["country_id"], tenant_id, db)

    for field, value in update_data.items():
        setattr(university, field, value)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(university)
    return university


@router.delete(
    "/universities/{university_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_university(
    university_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> None:
    """Delete a university within the caller's tenant."""
    university = _get_tenant_university(university_id, current_user, db)
    db.delete(university)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/programs", response_model=list[ProgramResponse])
def list_admin_programs(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> list[Program]:
    """List programs managed by the caller's tenant."""
    tenant_id = _require_tenant_scope(current_user)
    try:
        return (
            db.query(Program)
            .filter(Program.tenant_id == tenant_id)
            .order_by(Program.name)
            .all()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.post(
    "/programs",
    response_model=ProgramResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_program(
    payload: ProgramCreateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> Program:
    """Create a program scoped to a university in the caller's tenant."""
    tenant_id = _require_tenant_scope(current_user)
    _resolve_university_for_tenant(payload.university_id, tenant_id, db)

    program = Program(
        tenant_id=tenant_id,
        university_id=payload.university_id,
        name=payload.name,
    )
    db.add(program)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(program)
    return program


@router.patch("/programs/{program_id}", response_model=ProgramResponse)
def update_program(
    program_id: int,
    payload: ProgramUpdateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> Program:
    """Update a program's ``name`` and/or ``university_id`` within the caller's tenant."""
    tenant_id = _require_tenant_scope(current_user)
    program = _get_tenant_program(program_id, current_user, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be provided",
        )

    if "university_id" in update_data:
        _resolve_university_for_tenant(update_data["university_id"], tenant_id, db)

    for field, value in update_data.items():
        setattr(program, field, value)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(program)
    return program


@router.delete(
    "/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_program(
    program_id: int,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_permission(Permission.MASTER_DATA_MANAGE)),
    ],
    db: Session = Depends(get_db),
) -> None:
    """Delete a program within the caller's tenant."""
    program = _get_tenant_program(program_id, current_user, db)
    db.delete(program)
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None
