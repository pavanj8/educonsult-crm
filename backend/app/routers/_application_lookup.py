"""Shared tenant-scoped application lookup helpers."""

from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models.application import Application
from app.rbac.user import AuthenticatedUser

APPLICATION_DB_UNAVAILABLE_DETAIL = "Application service is temporarily unavailable"
APPLICATION_NOT_FOUND_DETAIL = "Application not found"


def get_tenant_application(
    application_id: int,
    current_user: AuthenticatedUser,
    db: Session,
    *,
    db_unavailable_detail: str = APPLICATION_DB_UNAVAILABLE_DETAIL,
) -> Application:
    """Load an application, returning 404 for missing or cross-tenant records."""
    try:
        application = db.get(Application, application_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=db_unavailable_detail,
        ) from None

    if application is None or (
        current_user.tenant_id is not None
        and application.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=APPLICATION_NOT_FOUND_DETAIL,
        )

    return application
