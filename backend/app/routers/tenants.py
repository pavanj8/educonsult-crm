"""Tenant management routes (E8; Journey J1; E10 logo upload + branding PATCH; E9 plan assignment; E45 plan & usage view)."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, selectinload

from app.auth.password import hash_password
from app.db.database import get_db
from app.email.owner_invite import send_owner_invite_email
from app.email.service import EmailDeliveryError
from app.models.plan import Plan, PlanTier
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.tenant import (
    AssignPlanRequest,
    PlanAndUsageResponse,
    PlanResponse,
    TenantBrandingUpdateRequest,
    TenantCreateRequest,
    TenantResponse,
    UsageSummary,
)
from app.storage import (
    LOGO_FILE_TOO_LARGE_DETAIL,
    LogoStorageError,
    LogoStorageService,
    get_logo_storage,
    validate_logo_file_size,
    validate_logo_file_type,
)

router = APIRouter()

_DB_UNAVAILABLE_DETAIL = "Tenant service is temporarily unavailable"
_EMAIL_UNAVAILABLE_DETAIL = "Unable to send owner invite email"
_STORAGE_UNAVAILABLE_DETAIL = "Logo storage is temporarily unavailable"
#: Stable 404 detail string used by both the genuine not-found and the
#: cross-tenant guard paths. Surfacing the same text in both cases is
#: intentional -- the cross-tenant guard must not leak tenant-id
#: existence (ADR-0004 tenant enumeration defense); the response code
#: is therefore indistinguishable from a real "not found".
TENANT_NOT_FOUND_DETAIL = "Tenant not found"
#: Stable 422 detail returned when ``PATCH /tenants/{id}/branding`` is
#: called with an empty payload (no fields supplied). Pydantic's
#: ``model_dump(exclude_unset=True)`` distinguishes "field present
#: with value None" from "field omitted entirely", so an entirely
#: empty body is the only thing that hits this branch.
BRANDING_EMPTY_PAYLOAD_DETAIL = "At least one branding field must be provided"

#: Defensive upper bound for the streaming read loop (E10 logo upload).
#: The user-facing 2 MB cap (see :data:`app.storage.validation.LOGO_MAX_FILE_BYTES`)
#: is enforced by :func:`validate_logo_file_size` after the stream completes;
#: this ceiling sits well above that value (50 MB) so its only job is to
#: keep the process RSS bounded under a hostile payload, even in the
#: unlikely event the post-read validator is ever relaxed.
_LOGO_STREAMING_CEILING_BYTES = 50 * 1024 * 1024


@router.post(
    "",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tenant(
    payload: TenantCreateRequest,
    _current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.TENANT_CREATE))
    ],
    db: Session = Depends(get_db),
) -> Tenant:
    """Create a new consultancy tenant and invite its owner (super admin only)."""
    try:
        existing_owner = (
            db.query(User)
            .filter(func.lower(User.email) == payload.owner_email)
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if existing_owner is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    tenant = Tenant(name=payload.name, slug=payload.slug)
    db.add(tenant)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tenant with this slug already exists",
        ) from None
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    temporary_password = secrets.token_urlsafe(16)
    owner = User(
        email=payload.owner_email,
        password_hash=hash_password(temporary_password),
        role=Role.CONSULTANCY_OWNER,
        tenant_id=tenant.id,
        branch_id=None,
    )
    db.add(owner)

    try:
        send_owner_invite_email(
            to_email=payload.owner_email,
            tenant_name=payload.name,
            temporary_password=temporary_password,
        )
    except EmailDeliveryError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_EMAIL_UNAVAILABLE_DETAIL,
        ) from None

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from None
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(tenant)
    return tenant


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    _current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.TENANT_READ))
    ],
    db: Session = Depends(get_db),
) -> list[Tenant]:
    """List all consultancy tenants (super admin only)."""
    try:
        return db.query(Tenant).order_by(Tenant.id).all()
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(
    _current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.BILLING_PLATFORM))
    ],
    db: Session = Depends(get_db),
) -> list[Plan]:
    """List platform plans in seed order, including retired tiers."""
    try:
        return db.query(Plan).order_by(Plan.id).all()
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    _current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.TENANT_READ))
    ],
    db: Session = Depends(get_db),
) -> Tenant:
    """Retrieve a single consultancy tenant by id (super admin only)."""
    try:
        tenant = db.get(Tenant, tenant_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=TENANT_NOT_FOUND_DETAIL,
        )

    return tenant


async def _read_logo_upload_bytes(upload: UploadFile) -> bytes:
    """Read the multipart logo upload into memory with a defensive upper bound.

    The user-facing 2 MB cap is enforced by
    :func:`app.storage.validation.validate_logo_file_size` after the
    stream completes — that is the rule from E10 / Journey J3 (logos
    are small branding assets, sized smaller than the 10 MB
    student-document cap). The streaming cap here is a **defensive
    safety net** set well above :data:`LOGO_MAX_FILE_BYTES` (50 MB) so
    the process RSS cannot be ballooned by an arbitrarily large
    payload even if the validator were ever removed in a future
    refactor. It is intentionally redundant today; do not lower it
    to ``LOGO_MAX_FILE_BYTES`` (the only line that should enforce the
    public cap is :func:`validate_logo_file_size`).
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > _LOGO_STREAMING_CEILING_BYTES:
            chunks.clear()
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=LOGO_FILE_TOO_LARGE_DETAIL,
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _load_tenant_for_logo_upload(
    tenant_id: int,
    current_user: AuthenticatedUser,
    db: Session,
) -> Tenant:
    """Load the target tenant or raise 404; enforce cross-tenant guard.

    The :class:`Permission.TENANT_UPDATE` gate (set by the
    ``Depends`` chain on the route) is granted to ``SUPER_ADMIN`` and
    ``CONSULTANCY_OWNER``. A consultancy owner from a *different*
    tenant must not be able to mutate another tenant's logo, so this
    helper surfaces a 404 (not a 403) to avoid leaking tenant-id
    existence. Super admins bypass the check (``tenant_id`` is
    ``None`` on the JWT).
    """
    try:
        tenant = db.get(Tenant, tenant_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=TENANT_NOT_FOUND_DETAIL,
        )

    if (
        current_user.role is not Role.SUPER_ADMIN
        and current_user.tenant_id is not None
        and current_user.tenant_id != tenant.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=TENANT_NOT_FOUND_DETAIL,
        )

    return tenant


@router.patch("/{tenant_id}/branding", response_model=TenantResponse)
def update_tenant_branding(
    tenant_id: int,
    payload: TenantBrandingUpdateRequest,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.TENANT_UPDATE))
    ],
    db: Session = Depends(get_db),
) -> Tenant:
    """Update a tenant's branding (logo, color, currency) (E10; Journey J3).

    Permission gate is ``TENANT_UPDATE``: super admins (platform-wide
    tenant management) and consultancy owners of the target tenant
    (own tenant's branding per Requirements §1 white-labeling).
    Owners from a *different* tenant are rejected by the explicit
    cross-tenant guard below, not by RBAC, so a tenant's owner can
    still update their own branding without listing it.
    """
    tenant = _load_tenant_for_logo_upload(tenant_id, current_user, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=BRANDING_EMPTY_PAYLOAD_DETAIL,
        )

    for field, value in update_data.items():
        setattr(tenant, field, value)

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(tenant)
    return tenant


@router.post(
    "/{tenant_id}/logo",
    response_model=TenantResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_tenant_logo(
    tenant_id: int,
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.TENANT_UPDATE))
    ],
    file: Annotated[UploadFile, File(description="The tenant logo image")],
    db: Session = Depends(get_db),
) -> Tenant:
    """Upload a tenant logo to S3-compatible storage and update ``logo_url``.

    Endpoint shape
    --------------
    ``POST /tenants/{tenant_id}/logo`` with a multipart/form-data body
    carrying:

    * ``file`` — the logo image bytes (required). Accepted types are
      PNG, JPG/JPEG, and WebP (see
      :data:`app.storage.validation.ALLOWED_LOGO_EXTENSIONS`). SVG is
      intentionally excluded because SVG is XML and can carry
      scripts — serving an attacker-controlled SVG from a CDN-backed
      URL is a known XSS vector that we explicitly avoid in v1.

    Authorization
    -------------
    Requires the ``tenant:update`` permission (granted to ``SUPER_ADMIN``
    and ``CONSULTANCY_OWNER``). The cross-tenant guard in
    :func:`_load_tenant_for_logo_upload` makes a consultancy owner
    uploading to a different tenant a 404 (so tenant-id existence is
    not leaked).

    On success the endpoint:

    1. Streams the multipart upload with a defensive ceiling.
    2. Validates the file size (<=2 MB) and extension / content-type.
    3. Persists the bytes to the S3-compatible store via
       :class:`LogoStorageService` and receives the object key.
    4. Writes that key to ``Tenant.logo_url`` (replacing any previous
       value) and commits the row.
    5. Returns the updated :class:`TenantResponse`.

    Errors
    ------
    * 400 — ``file`` form field is missing, empty, or has no filename.
    * 401 — caller is not authenticated.
    * 403 — caller lacks ``tenant:update``.
    * 404 — tenant does not exist or belongs to a different tenant
      (cross-tenant guard surfaces as 404, not 403, to avoid leaking
      tenant-id existence).
    * 413 — uploaded logo exceeds the 2 MB cap.
    * 415 — uploaded logo's extension is not in
      :data:`app.storage.validation.ALLOWED_LOGO_EXTENSIONS` (PNG /
      JPG/JPEG / WebP), or its ``Content-Type`` does not match the
      extension.
    * 503 — logo storage backend is unreachable / rejected the
      upload, or the database is unavailable while reading / writing
      the row.

    Traceability
    ------------
    * Requirements §1 (White-labeling: each tenant can upload a logo).
    * Journey J3 (Consultancy Owner completes tenant profile).
    * Epic E10 (Tenant Branding & Profile); this endpoint is the
      upload half. Sibling ticket #110 owns ``PATCH
      /tenants/{id}/branding`` for non-upload updates (brand_color
      / currency); the frontend settings page is #112 and the
      frontend theming is #113.
    """
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'file' form field",
        )
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is missing a filename",
        )

    tenant = _load_tenant_for_logo_upload(tenant_id, current_user, db)

    content = await _read_logo_upload_bytes(file)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded logo is empty",
        )

    content_type = file.content_type
    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is missing a Content-Type header",
        )
    original_filename = file.filename

    # E10 / Journey J3 — logo size cap and type allow-list enforced
    # before talking to storage so an oversized / wrong-type upload
    # never costs a storage round-trip.
    validate_logo_file_size(len(content))
    validate_logo_file_type(filename=original_filename, content_type=content_type)

    storage: LogoStorageService = get_logo_storage()
    try:
        storage_path = storage.store_logo(
            tenant_id=tenant.id,
            original_filename=original_filename,
            content=content,
            content_type=content_type,
        )
    except LogoStorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_STORAGE_UNAVAILABLE_DETAIL,
        ) from None

    tenant.logo_url = storage_path

    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.refresh(tenant)
    return tenant


#: Stable 404 detail used by the assign/change-plan endpoint when the
#: target tenant does not exist. Shared with the existing tenant-detail
#: endpoint so a probe cannot tell "tenant id used to exist" from "tenant
#: id was never valid".
_PLAN_TENANT_NOT_FOUND_DETAIL = TENANT_NOT_FOUND_DETAIL
#: Stable 404 detail for "the requested plan code does not exist in the
#: catalog". Surfaced as 404 (not 400) because a stale plan code on a
#: retired tier is semantically the same as "this row is not in the
#: catalog right now".
_PLAN_NOT_FOUND_DETAIL = "Plan not found"
#: Stable 409 detail for "the requested plan exists but is retired
#: (``is_active=False``)". We do not allow re-activating retired tiers
#: via this endpoint -- that is a platform-admin concern, not a
#: super-admin tenant-management one.
_PLAN_RETIRED_DETAIL = "Plan is no longer active"


def _resolve_plan_for_assignment(plan_code: str, db: Session) -> Plan:
    """Resolve a ``plan_code`` payload to a catalog row, or raise 404/409.

    Failure modes (in order of preference):

    * Unknown code -- 404 ``_PLAN_NOT_FOUND_DETAIL``. The schema's
      ``plan_code`` validator already rejects *malformed* codes
      (anything outside the three ``PlanTier`` values) as 422; this
      branch handles the "schema-valid but the catalog row was
      removed" case.
    * Retired tier (``is_active=False``) -- 409 ``_PLAN_RETIRED_DETAIL``.
      A retired plan is a *known* tier, just not currently sellable;
      the assign endpoint must not silently re-activate it.

    The endpoint is super-admin only, so a 404 here is honest about
    plan-code existence (cross-tenant probing is not a concern -- the
    platform has exactly one catalog).
    """
    try:
        plan = (
            db.query(Plan)
            .filter(Plan.code == PlanTier(plan_code))
            .one_or_none()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PLAN_NOT_FOUND_DETAIL,
        )

    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_PLAN_RETIRED_DETAIL,
        )

    return plan


@router.post(
    "/{tenant_id}/plan",
    response_model=TenantResponse,
    status_code=status.HTTP_200_OK,
)
def assign_tenant_plan(
    tenant_id: int,
    payload: AssignPlanRequest,
    _current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.BILLING_PLATFORM))
    ],
    db: Session = Depends(get_db),
) -> Tenant:
    """Assign or change a tenant's subscription plan (E9 task #106; Journey J2).

    Super-admin only (``billing:platform`` permission, which is granted
    to ``SUPER_ADMIN`` and to no other role). The endpoint:

    1. Loads the target tenant (404 ``_PLAN_TENANT_NOT_FOUND_DETAIL``
       if missing).
    2. Resolves the requested ``plan_code`` against the platform-level
       catalog (404 if unknown, 409 if retired) via
       :func:`_resolve_plan_for_assignment`.
    3. Writes ``Tenant.plan_id`` (replacing any previous value --
       "assign or change" in the epic language) and commits.
    4. Refreshes the tenant and returns the updated
       :class:`TenantResponse` (with the nested ``plan`` payload).

    The endpoint is idempotent in the sense that calling it twice with
    the same ``plan_code`` does not raise -- it just re-writes the same
    FK. A change to a *different* plan is a real write and updates
    ``Tenant.updated_at`` via the standard SQLAlchemy ``onupdate``
    hook. There is no "unset plan" body (the column is nullable but
    removing a plan is a platform-admin operation, not a super-admin
    tenant-management one).

    Errors
    ------
    * 401 -- caller is not authenticated.
    * 403 -- caller lacks ``billing:platform``.
    * 404 -- tenant does not exist, or ``plan_code`` is unknown.
    * 409 -- plan exists but is retired (``is_active=False``).
    * 422 -- ``plan_code`` is missing, empty, or not one of the three
      ``PlanTier`` values (schema-layer validation).
    * 503 -- database is unavailable.

    Traceability
    ------------
    * Requirements §4 (Billing & Subscription: 3 tiers, super-admin
      platform-level).
    * Journey J2 (Super Admin sets/updates a tenant's subscription
      plan).
    * Epic E9 (Subscription Plan Assignment); sibling ticket #105 owns
      the catalog itself and #107 owns the per-tier limit enforcement
      (a tenant cannot be assigned a tier that would immediately be
      over its limits -- the assign endpoint deliberately does NOT
      enforce that here; the limit checks live in their own endpoint
      so the assign/change API stays a pure state-change surface).
    """
    try:
        tenant = db.get(Tenant, tenant_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PLAN_TENANT_NOT_FOUND_DETAIL,
        )

    plan = _resolve_plan_for_assignment(payload.plan_code, db)

    tenant.plan_id = plan.id

    try:
        db.commit()
    except IntegrityError:
        # The only realistic FK violation here would be a race where
        # the plan row was deleted between the resolution above and
        # the commit. The schema has ``ondelete="RESTRICT"`` so a
        # concurrent delete would fail with IntegrityError; we treat
        # that the same as a 404 on the plan code.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PLAN_NOT_FOUND_DETAIL,
        ) from None
    except OperationalError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    db.expire_all()
    refreshed = (
        db.query(Tenant)
        .options(selectinload(Tenant.plan))
        .filter(Tenant.id == tenant.id)
        .one()
    )
    return refreshed


@router.get("/me/plan-usage", response_model=PlanAndUsageResponse)
def get_my_plan_and_usage(
    current_user: Annotated[
        AuthenticatedUser, Depends(require_permission(Permission.BILLING_READ_OWN))
    ],
    db: Session = Depends(get_db),
) -> PlanAndUsageResponse:
    """Return the current owner's tenant plan and usage summary (E45; Journey J38).

    Consultancy owner only (``billing:read_own`` permission). The endpoint:

    1. Validates the caller has a ``tenant_id`` set (owners always do;
       the permission check rejects students and other roles).
    2. Loads the tenant's assigned plan via ``Tenant.plan_id`` (returns
       ``None`` if the tenant has no plan yet -- the owner UI should
       prompt the owner to contact the platform).
    3. Counts the tenant's current usage of branches, staff, and students
       (the same counts used by the E9 task #107 enforcement layer).
    4. Returns both the plan details and the current usage summary in
       a single response.

    Why ``/me/plan-usage`` and not ``/tenants/{id}/plan-usage``
    -----------------------------------------------------------
    Journey J38 is explicitly "Consultancy Owner views current plan &
    usage" -- the actor is the owner viewing their *own* tenant's
    state, not an admin viewing another tenant. The ``/me`` prefix
    makes the self-only nature explicit and avoids exposing a
    cross-tenant enumeration surface. Super admins already have the
    platform-wide billing status overview (E47, J40) for
    cross-tenant visibility.

    Errors
    ------
    * 401 -- caller is not authenticated.
    * 403 -- caller lacks ``billing:read_own`` (granted only to
      ``CONSULTANCY_OWNER``).
    * 503 -- database is unavailable.

    Traceability
    ------------
    * Requirements §4 (Billing & Subscription: 3 tiers).
    * Journey J38 (Consultancy Owner views current plan & usage).
    * Epic E45 (Owner Plan & Usage View); this endpoint is the backend half.
    """
    from app.models.branch import Branch
    from app.models.user import User

    if current_user.tenant_id is None:
        # A CONSULTANCY_OWNER should never have a NULL tenant_id (the
        # create-tenant endpoint sets it), but we guard defensively --
        # this is a billing surface, so a missing tenant association
        # is a hard 500 class error, not a soft 404.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    # Load the tenant with its plan relationship in one query.
    try:
        tenant = (
            db.query(Tenant)
            .options(selectinload(Tenant.plan))
            .filter(Tenant.id == current_user.tenant_id)
            .one()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    # Count branches for this tenant.
    try:
        branches_used = (
            db.execute(
                select(func.count())
                .select_from(Branch)
                .where(Branch.tenant_id == current_user.tenant_id)
            )
            .scalar_one()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    # Count staff (all non-student roles) for this tenant.
    # Staff includes: consultancy_owner, branch_manager, counselor,
    # document_verifier, visa_processor, receptionist. This matches the
    # E43 platform-wide-stats endpoint which counts all non-student roles.
    try:
        staff_used = (
            db.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.tenant_id == current_user.tenant_id,
                    User.role != Role.STUDENT,
                )
            )
            .scalar_one()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    # Count students for this tenant.
    try:
        students_used = (
            db.execute(
                select(func.count())
                .select_from(User)
                .where(
                    User.tenant_id == current_user.tenant_id,
                    User.role == Role.STUDENT,
                )
            )
            .scalar_one()
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_DB_UNAVAILABLE_DETAIL,
        ) from None

    # Extract the plan limits (or None if no plan / unlimited).
    plan = tenant.plan
    if plan is not None:
        branches_limit = plan.max_branches
        staff_limit = plan.max_staff
        students_limit = plan.max_students
    else:
        branches_limit = None
        staff_limit = None
        students_limit = None

    usage = UsageSummary(
        branches_used=int(branches_used),
        branches_limit=branches_limit,
        staff_used=int(staff_used),
        staff_limit=staff_limit,
        students_used=int(students_used),
        students_limit=students_limit,
    )

    return {"plan": plan, "usage": usage}


__all__ = ["router"]
