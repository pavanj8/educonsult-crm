"""Tenant management routes (E8; Journey J1; E10 logo upload)."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.db.database import get_db
from app.email.owner_invite import send_owner_invite_email
from app.email.service import EmailDeliveryError
from app.models.tenant import Tenant
from app.models.user import User
from app.rbac import Permission
from app.rbac.dependencies import require_permission
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser
from app.schemas.tenant import TenantCreateRequest, TenantResponse
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
            detail="Tenant not found",
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
            detail="Tenant not found",
        )

    if (
        current_user.role is not Role.SUPER_ADMIN
        and current_user.tenant_id is not None
        and current_user.tenant_id != tenant.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

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


__all__ = ["router"]
