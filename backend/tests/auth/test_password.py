import pytest

from app.auth import hash_password, verify_password
from app.auth.password_policy import validate_password_strength


def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("S3curePass!")
    assert hashed.startswith("$2")


def test_hash_password_uses_unique_salt():
    password = "same-password"
    first = hash_password(password)
    second = hash_password(password)
    assert first != second


def test_verify_password_accepts_correct_password():
    password = "correct-horse-battery-staple"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("actual-password")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_rejects_empty_password():
    hashed = hash_password("non-empty")
    assert verify_password("", hashed) is False


def test_validate_password_strength_accepts_strong_password():
    assert validate_password_strength("StudentPass1!") == "StudentPass1!"


def test_validate_password_strength_rejects_common_password():
    with pytest.raises(ValueError, match="too common"):
        validate_password_strength("password")


def test_validate_password_strength_rejects_short_password():
    with pytest.raises(ValueError, match="at least"):
        validate_password_strength("Ab1!")


def test_validate_password_strength_rejects_whitespace_only():
    with pytest.raises(ValueError, match="whitespace"):
        validate_password_strength("   ")
