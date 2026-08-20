"""Strong password policy validation (Requirements §8; E7 foundation)."""

import re

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72

_COMMON_WEAK_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "12345678",
        "123456789",
        "qwerty123",
        "letmein",
        "welcome",
        "admin123",
    }
)

_UPPERCASE = re.compile(r"[A-Z]")
_LOWERCASE = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def validate_password_strength(password: str) -> str:
    """Validate password meets the platform strong-password policy."""
    if not password or not password.strip():
        raise ValueError("Password must not be empty or whitespace only")

    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )

    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must not exceed {PASSWORD_MAX_LENGTH} characters"
        )

    if password.lower() in _COMMON_WEAK_PASSWORDS:
        raise ValueError("Password is too common; choose a stronger password")

    if not _UPPERCASE.search(password):
        raise ValueError("Password must contain at least one uppercase letter")

    if not _LOWERCASE.search(password):
        raise ValueError("Password must contain at least one lowercase letter")

    if not _DIGIT.search(password):
        raise ValueError("Password must contain at least one digit")

    if not _SPECIAL.search(password):
        raise ValueError("Password must contain at least one special character")

    return password
