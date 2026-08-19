"""JWT configuration (E5 auth; Requirements §8)."""

import os
from datetime import timedelta

_DEFAULT_SECRET = "dev-only-change-me"
_DEFAULT_ALGORITHM = "HS256"
_DEFAULT_ACCESS_EXPIRE_MINUTES = 15
_DEFAULT_REFRESH_EXPIRE_DAYS = 7


def jwt_secret_key() -> str:
    return os.environ.get("JWT_SECRET_KEY", _DEFAULT_SECRET)


def jwt_algorithm() -> str:
    return os.environ.get("JWT_ALGORITHM", _DEFAULT_ALGORITHM)


def access_token_lifetime() -> timedelta:
    minutes = int(
        os.environ.get(
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
            str(_DEFAULT_ACCESS_EXPIRE_MINUTES),
        )
    )
    return timedelta(minutes=minutes)


def refresh_token_lifetime() -> timedelta:
    days = int(
        os.environ.get(
            "JWT_REFRESH_TOKEN_EXPIRE_DAYS",
            str(_DEFAULT_REFRESH_EXPIRE_DAYS),
        )
    )
    return timedelta(days=days)
