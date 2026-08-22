"""End-to-end acceptance tests for the password-reset flow (issue #94)."""

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


from app.auth.password import verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.rbac.roles import Role
from tests.factories.users import make_db_user


def _issue_reset_token(client, db_session, user):
    with patch("app.routers.auth.send_password_reset_email") as send_email:
        response = client.post(
            "/auth/forgot-password", json={"email": user.email}
        )
    assert response.status_code == 200
    token = send_email.call_args.kwargs["reset_url"].split("token=", 1)[1]
    return token


def _make_reset_token(db_session, user, token, *, expired=False):
    now = datetime.now(timezone.utc)
    row = PasswordResetToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=(
            now - timedelta(minutes=1) if expired else now + timedelta(hours=1)
        ),
        created_at=now,
        updated_at=now,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_password_reset_happy_path_changes_password(client, db_session):
    user = make_db_user(
        db_session,
        Role.STUDENT,
        email="student.reset@example.test",
        password="Original1!",
    )

    token = _issue_reset_token(client, db_session, user)

    reset = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Replacement1!"},
    )

    assert reset.status_code == 200
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("Replacement1!", refreshed.password_hash)
    assert not verify_password("Original1!", refreshed.password_hash)

    login = client.post(
        "/auth/login",
        json={"email": user.email, "password": "Replacement1!"},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


def test_password_reset_rejects_expired_and_invalid_tokens(client, db_session):
    user = make_db_user(
        db_session,
        Role.STUDENT,
        email="expired.reset@example.test",
    )

    invalid = client.post(
        "/auth/reset-password",
        json={"token": "not-a-real-reset-token", "new_password": "Replacement1!"},
    )
    assert invalid.status_code == 400
    assert invalid.json() == {"detail": "Invalid or expired reset token"}

    forgot = client.post(
        "/auth/forgot-password",
        json={"email": user.email},
    )
    assert forgot.status_code == 200
    token = send_password_reset_email.call_args.kwargs["reset_url"].split(
        "token=", 1
    )[1]

    row = db_session.query(PasswordResetToken).filter_by(user_id=user.id).one()
    row.expires_at = row.created_at.replace(year=row.created_at.year - 1)
    db_session.commit()

    expired = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Replacement1!"},
    )
    assert expired.status_code == 400
    assert expired.json() == {"detail": "Invalid or expired reset token"}

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("test-password", refreshed.password_hash)


def test_password_reset_token_is_single_use(client, db_session):
    user = make_db_user(
        db_session,
        Role.STUDENT,
        email="single-use.reset@example.test",
    )
    forgot = client.post(
        "/auth/forgot-password",
        json={"email": user.email},
    )
    assert forgot.status_code == 200
    token = send_password_reset_email.call_args.kwargs["reset_url"].split(
        "token=", 1
    )[1]

    first = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Replacement1!"},
    )
    second = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "AnotherPass1!"},
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json() == {"detail": "Invalid or expired reset token"}
    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("Replacement1!", refreshed.password_hash)
