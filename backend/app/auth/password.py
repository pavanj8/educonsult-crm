"""Password hashing utilities (E5 auth; Requirements §8)."""

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash suitable for storage in ``User.password_hash``."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True when ``plain_password`` matches ``hashed_password``."""
    return _pwd_context.verify(plain_password, hashed_password)
