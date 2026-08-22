"""Tests for the password hashing utility and strong-password policy (E5/E7).

Issue #97 acceptance criteria covered here:

* The policy rejects passwords missing any required character class
  (uppercase, lowercase, digit, special character).
* The policy rejects passwords shorter than the documented minimum.
* The policy rejects passwords longer than the documented maximum
  (bcrypt's 72-byte input ceiling).
* The policy rejects whitespace-only and empty values.
* The policy rejects a curated set of trivially common passwords.
* A valid strong password is accepted and returned unchanged.

The endpoint-level integration tests for ``/auth/register-student`` and
``/auth/reset-password`` live in their own modules and exercise the same
validator through Pydantic / the router, respectively.
"""

import pytest

from app.auth import hash_password, verify_password
from app.auth.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    validate_password_strength,
)


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


def test_validate_password_strength_returns_unchanged_when_valid():
    """The validator returns the input unchanged on success so callers can chain it."""
    password = "AnotherGood1!Pass"
    assert validate_password_strength(password) is password or (
        validate_password_strength(password) == password
    )


def test_validate_password_strength_accepts_minimum_length_password():
    """A password that is exactly the documented minimum length is accepted."""
    # PASSWORD_MIN_LENGTH chars, with all four character classes present.
    password = "Aa1!" + "x" * (PASSWORD_MIN_LENGTH - 4)
    assert len(password) == PASSWORD_MIN_LENGTH
    assert validate_password_strength(password) == password


def test_validate_password_strength_rejects_empty_password():
    with pytest.raises(ValueError, match="whitespace"):
        validate_password_strength("")


def test_validate_password_strength_rejects_whitespace_only():
    with pytest.raises(ValueError, match="whitespace"):
        validate_password_strength("   ")


def test_validate_password_strength_rejects_short_password():
    with pytest.raises(ValueError, match="at least"):
        validate_password_strength("Ab1!")


def test_validate_password_strength_rejects_password_one_below_minimum():
    with pytest.raises(ValueError, match="at least"):
        # PASSWORD_MIN_LENGTH - 1 characters long, but otherwise shaped
        # like a strong password -- the length check must trip first.
        password = "Aa1!" + "x" * (PASSWORD_MIN_LENGTH - 5)
        assert len(password) == PASSWORD_MIN_LENGTH - 1
        validate_password_strength(password)


def test_validate_password_strength_rejects_over_maximum_length_password():
    """bcrypt truncates input past 72 bytes, so we reject it explicitly."""
    # PASSWORD_MAX_LENGTH + 1 characters long.
    password = "Aa1!" + "x" * (PASSWORD_MAX_LENGTH - 3)
    assert len(password) == PASSWORD_MAX_LENGTH + 1
    with pytest.raises(ValueError, match="exceed"):
        validate_password_strength(password)


def test_validate_password_strength_rejects_missing_uppercase():
    with pytest.raises(ValueError, match="uppercase"):
        validate_password_strength("all-lower-1!")


def test_validate_password_strength_rejects_missing_lowercase():
    with pytest.raises(ValueError, match="lowercase"):
        validate_password_strength("ALL-UPPER-1!")


def test_validate_password_strength_rejects_missing_digit():
    with pytest.raises(ValueError, match="digit"):
        validate_password_strength("NoDigitsHere!")


def test_validate_password_strength_rejects_missing_special_character():
    with pytest.raises(ValueError, match="special"):
        validate_password_strength("NoSpecials1Aa")


def test_validate_password_strength_rejects_common_password():
    with pytest.raises(ValueError, match="too common"):
        validate_password_strength("password")


def test_validate_password_strength_rejects_common_password_case_insensitive():
    """The common-password check must be case-insensitive (e.g. 'PASSWORD')."""
    with pytest.raises(ValueError, match="too common"):
        validate_password_strength("PASSWORD")


def test_validate_password_strength_rejects_common_password_with_strong_shape():
    """A common weak password (lowercased form in the curated list) is rejected.

    'password1' is in the curated weak list. Even though it already has all
    four character classes, the common-password guard fires first and the
    password is rejected.
    """
    with pytest.raises(ValueError, match="too common"):
        validate_password_strength("Password1")
