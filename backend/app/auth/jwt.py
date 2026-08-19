"""JWT access and refresh token utilities (E5 auth; Requirements §8)."""

from datetime import UTC, datetime, timedelta

import jwt

from app.auth.config import (
    access_token_lifetime,
    jwt_algorithm,
    jwt_secret_key,
    refresh_token_lifetime,
)
from app.rbac.roles import Role
from app.rbac.user import AuthenticatedUser

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class JWTError(Exception):
    """Base error for JWT creation or verification failures."""


class TokenExpiredError(JWTError):
    """Raised when a token is structurally valid but past its expiry."""


class InvalidTokenError(JWTError):
    """Raised when a token is malformed, wrongly signed, or has invalid claims."""


def _encode_token(
    user: AuthenticatedUser,
    *,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if user.tenant_id is not None:
        payload["tenant_id"] = user.tenant_id
    if user.branch_id is not None:
        payload["branch_id"] = user.branch_id
    return jwt.encode(payload, jwt_secret_key(), algorithm=jwt_algorithm())


def create_access_token(user: AuthenticatedUser) -> str:
    """Return a signed JWT access token for ``user``."""
    return _encode_token(
        user,
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=access_token_lifetime(),
    )


def create_refresh_token(user: AuthenticatedUser) -> str:
    """Return a signed JWT refresh token for ``user``."""
    return _encode_token(
        user,
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=refresh_token_lifetime(),
    )


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            jwt_secret_key(),
            algorithms=[jwt_algorithm()],
            options={"require": ["exp", "iat", "sub", "role", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid token") from exc


def _user_from_payload(payload: dict, *, expected_type: str) -> AuthenticatedUser:
    token_type = payload.get("type")
    if token_type != expected_type:
        raise InvalidTokenError(f"Expected {expected_type} token")

    try:
        user_id = int(payload["sub"])
        role = Role(payload["role"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Invalid token claims") from exc

    tenant_id = payload.get("tenant_id")
    branch_id = payload.get("branch_id")
    if tenant_id is not None:
        tenant_id = int(tenant_id)
    if branch_id is not None:
        branch_id = int(branch_id)

    return AuthenticatedUser(
        id=user_id,
        role=role,
        tenant_id=tenant_id,
        branch_id=branch_id,
    )


def verify_access_token(token: str) -> AuthenticatedUser:
    """Decode and validate an access token, returning the authenticated principal."""
    return _user_from_payload(_decode_token(token), expected_type=TOKEN_TYPE_ACCESS)


def verify_refresh_token(token: str) -> AuthenticatedUser:
    """Decode and validate a refresh token, returning the authenticated principal."""
    return _user_from_payload(_decode_token(token), expected_type=TOKEN_TYPE_REFRESH)
