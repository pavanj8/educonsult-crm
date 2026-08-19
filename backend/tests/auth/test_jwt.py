from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
from app.auth.config import jwt_algorithm, jwt_secret_key
from app.rbac.roles import Role
from tests.factories.users import make_authenticated_user


def test_create_access_token_returns_three_part_jwt():
    user = make_authenticated_user(Role.COUNSELOR)
    token = create_access_token(user)
    assert isinstance(token, str)
    assert len(token.split(".")) == 3


def test_verify_access_token_round_trips_user_claims():
    user = make_authenticated_user(
        Role.BRANCH_MANAGER,
        user_id=42,
        tenant_id=7,
        branch_id=3,
    )
    token = create_access_token(user)
    verified = verify_access_token(token)
    assert verified == user


def test_verify_access_token_super_admin_without_tenant_or_branch():
    user = make_authenticated_user(
        Role.SUPER_ADMIN,
        user_id=1,
        tenant_id=None,
        branch_id=None,
    )
    token = create_access_token(user)
    verified = verify_access_token(token)
    assert verified.id == 1
    assert verified.role == Role.SUPER_ADMIN
    assert verified.tenant_id is None
    assert verified.branch_id is None


def test_create_refresh_token_and_verify_round_trip():
    user = make_authenticated_user(Role.STUDENT, user_id=99, tenant_id=2, branch_id=5)
    token = create_refresh_token(user)
    verified = verify_refresh_token(token)
    assert verified == user


def test_verify_access_token_rejects_refresh_token():
    user = make_authenticated_user(Role.COUNSELOR)
    refresh_token = create_refresh_token(user)
    with pytest.raises(InvalidTokenError, match="Expected access token"):
        verify_access_token(refresh_token)


def test_verify_refresh_token_rejects_access_token():
    user = make_authenticated_user(Role.COUNSELOR)
    access_token = create_access_token(user)
    with pytest.raises(InvalidTokenError, match="Expected refresh token"):
        verify_refresh_token(access_token)


def test_verify_access_token_rejects_expired_token(monkeypatch):
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "0")
    user = make_authenticated_user(Role.RECEPTIONIST)
    token = create_access_token(user)
    with pytest.raises(TokenExpiredError):
        verify_access_token(token)


def test_verify_access_token_rejects_tampered_signature():
    user = make_authenticated_user(Role.COUNSELOR)
    token = create_access_token(user)
    tampered = f"{token}tampered"
    with pytest.raises(InvalidTokenError):
        verify_access_token(tampered)


def test_verify_access_token_rejects_token_signed_with_wrong_secret():
    user = make_authenticated_user(Role.COUNSELOR, user_id=10)
    now = datetime.now(UTC)
    payload = {
        "sub": "10",
        "role": Role.COUNSELOR.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "tenant_id": 1,
        "branch_id": 1,
    }
    wrong_secret_token = jwt.encode(payload, "wrong-secret", algorithm=jwt_algorithm())
    with pytest.raises(InvalidTokenError):
        verify_access_token(wrong_secret_token)


def test_verify_access_token_rejects_malformed_token():
    with pytest.raises(InvalidTokenError):
        verify_access_token("not-a-jwt")


def test_verify_access_token_rejects_token_missing_required_claims():
    now = datetime.now(UTC)
    payload = {
        "sub": "1",
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    token = jwt.encode(payload, jwt_secret_key(), algorithm=jwt_algorithm())
    with pytest.raises(InvalidTokenError):
        verify_access_token(token)


def test_access_and_refresh_tokens_use_different_type_claims():
    user = make_authenticated_user(Role.CONSULTANCY_OWNER, tenant_id=4)
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    access_payload = jwt.decode(
        access_token,
        jwt_secret_key(),
        algorithms=[jwt_algorithm()],
    )
    refresh_payload = jwt.decode(
        refresh_token,
        jwt_secret_key(),
        algorithms=[jwt_algorithm()],
    )

    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert access_payload["sub"] == refresh_payload["sub"]
    assert access_payload["role"] == refresh_payload["role"]
